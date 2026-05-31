# ─────────────────────────────────────────────────────────────
# main.tf — Terraform IaC для SpeakUP ML-инфраструктуры
# Провайдер: Yandex Cloud
# Окружение: MVP (docker-compose на одной VM)
# Миграция на k8s: при > 10k DAU или > 3 ML-сервисов (см. docs/)
# ─────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = "~> 0.105"
    }
  }

  # Удалённый backend — хранение state в Object Storage Yandex Cloud
  # Раскомментировать после создания бакета вручную (bootstrap)
  # backend "s3" {
  #   endpoint   = "storage.yandexcloud.net"
  #   bucket     = "speakup-tf-state"
  #   key        = "prod/terraform.tfstate"
  #   region     = "ru-central1"
  #   access_key = var.yandex_access_key
  #   secret_key = var.yandex_secret_key
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  # }
}

provider "yandex" {
  token     = var.yandex_token
  folder_id = var.yandex_folder_id
  zone      = var.yandex_cloud_zone
}

# ─────────────────────────────────────────────────────────────
# NETWORK
# ─────────────────────────────────────────────────────────────

resource "yandex_vpc_network" "speakup_net" {
  name   = "${var.project_name}-network"
  labels = var.common_tags
}

resource "yandex_vpc_subnet" "speakup_subnet" {
  name           = "${var.project_name}-subnet"
  zone           = var.yandex_cloud_zone
  network_id     = yandex_vpc_network.speakup_net.id
  v4_cidr_blocks = [var.subnet_cidr]
  labels         = var.common_tags
}

# Security Group — только нужные порты
resource "yandex_vpc_security_group" "speakup_sg" {
  name       = "${var.project_name}-sg"
  network_id = yandex_vpc_network.speakup_net.id
  labels     = var.common_tags

  # SSH
  ingress {
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "SSH access"
  }

  # Matching API
  ingress {
    protocol       = "TCP"
    port           = 8000
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "Matching API (FastAPI)"
  }

  # Grafana
  ingress {
    protocol       = "TCP"
    port           = 3000
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "Grafana dashboard"
  }

  # MLflow
  ingress {
    protocol       = "TCP"
    port           = 5000
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "MLflow tracking server"
  }

  # Airflow
  ingress {
    protocol       = "TCP"
    port           = 8080
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "Airflow webserver"
  }

  # Prometheus
  ingress {
    protocol       = "TCP"
    port           = 9090
    v4_cidr_blocks = ["10.0.0.0/8"]
    description    = "Prometheus (internal only)"
  }

  # Весь исходящий трафик разрешён
  egress {
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    description    = "All outbound traffic"
  }
}

# ─────────────────────────────────────────────────────────────
# COMPUTE — MVP: одна VM с docker-compose
# ─────────────────────────────────────────────────────────────

data "yandex_compute_image" "ubuntu" {
  family = var.vm_image_family
}

resource "yandex_compute_disk" "speakup_disk" {
  name   = "${var.project_name}-disk"
  type   = "network-ssd"
  size   = var.vm_disk_size_gb
  image_id = data.yandex_compute_image.ubuntu.id
  labels = var.common_tags
}

resource "yandex_compute_instance" "speakup_vm" {
  name        = "${var.project_name}-vm-${var.environment}"
  platform_id = "standard-v3"
  zone        = var.yandex_cloud_zone
  labels      = var.common_tags

  resources {
    cores         = var.vm_cores
    memory        = var.vm_memory_gb
    core_fraction = 100
  }

  boot_disk {
    disk_id = yandex_compute_disk.speakup_disk.id
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.speakup_subnet.id
    nat                = true  # публичный IP для деплоя
    security_group_ids = [yandex_vpc_security_group.speakup_sg.id]
  }

  metadata = {
    ssh-keys = "ubuntu:${file(var.ssh_public_key_path)}"

    # cloud-init: установка Docker + docker-compose при первом запуске
    user-data = <<-CLOUDINIT
      #cloud-config
      packages:
        - docker.io
        - docker-compose-v2
        - git
        - curl
        - htop

      runcmd:
        - systemctl enable docker
        - systemctl start docker
        - usermod -aG docker ubuntu
        - mkdir -p /opt/speakup
        - git clone https://github.com/${var.docker_registry}/speakup-ml.git /opt/speakup
        - cd /opt/speakup && docker compose up -d
        - echo "SpeakUP ML stack deployed at $(date)" >> /var/log/speakup-deploy.log
      CLOUDINIT
  }

  scheduling_policy {
    preemptible = var.environment != "prod"  # preemptible в dev для экономии
  }
}

# Статический публичный IP (не меняется при рестарте)
resource "yandex_vpc_address" "speakup_static_ip" {
  name   = "${var.project_name}-static-ip"
  labels = var.common_tags

  external_ipv4_address {
    zone_id = var.yandex_cloud_zone
  }
}

# ─────────────────────────────────────────────────────────────
# MANAGED POSTGRESQL — Feature Store (offline)
# ─────────────────────────────────────────────────────────────

resource "yandex_mdb_postgresql_cluster" "speakup_pg" {
  name        = "${var.project_name}-postgres"
  environment = upper(var.environment)
  network_id  = yandex_vpc_network.speakup_net.id
  labels      = var.common_tags

  config {
    version = var.pg_version

    resources {
      resource_preset_id = var.pg_resource_preset
      disk_size          = var.pg_disk_size_gb
      disk_type_id       = var.pg_disk_type
    }

    postgresql_config = {
      # Оптимизации для ML-нагрузки
      max_connections                = 100
      shared_buffers                 = 536870912   # 512MB
      effective_cache_size           = 1610612736  # 1.5GB
      maintenance_work_mem           = 134217728   # 128MB
      checkpoint_completion_target   = "0.9"
      wal_buffers                    = 16777216    # 16MB
      default_statistics_target      = 100
    }
  }

  host {
    zone      = var.yandex_cloud_zone
    subnet_id = yandex_vpc_subnet.speakup_subnet.id
  }
}

resource "yandex_mdb_postgresql_database" "speakup_db" {
  cluster_id = yandex_mdb_postgresql_cluster.speakup_pg.id
  name       = var.pg_database_name
  owner      = var.pg_user
}

resource "yandex_mdb_postgresql_user" "speakup_pg_user" {
  cluster_id = yandex_mdb_postgresql_cluster.speakup_pg.id
  name       = var.pg_user
  password   = var.pg_password

  grants = []

  permission {
    database_name = var.pg_database_name
  }

  settings = {
    default_transaction_isolation = "read committed"
    lock_timeout                  = 10000
    log_min_duration_statement    = 5000  # логировать запросы > 5 сек
  }
}

# ─────────────────────────────────────────────────────────────
# MANAGED REDIS — Feature Store (online / cache)
# ─────────────────────────────────────────────────────────────

resource "yandex_mdb_redis_cluster" "speakup_redis" {
  name        = "${var.project_name}-redis"
  environment = upper(var.environment)
  network_id  = yandex_vpc_network.speakup_net.id
  labels      = var.common_tags

  config {
    version  = var.redis_version
    password = var.redis_password

    # TTL для feature cache — 1 час (matching predictions)
    maxmemory_policy = "allkeys-lru"
  }

  resources {
    resource_preset_id = var.redis_resource_preset
    disk_size          = var.redis_disk_size_gb
    disk_type_id       = "network-ssd"
  }

  host {
    zone      = var.yandex_cloud_zone
    subnet_id = yandex_vpc_subnet.speakup_subnet.id
  }
}

# ─────────────────────────────────────────────────────────────
# OBJECT STORAGE — аудио (TTL 90d) + MLflow artifacts
# ─────────────────────────────────────────────────────────────

resource "yandex_storage_bucket" "speakup_artifacts" {
  bucket     = var.bucket_name
  access_key = var.yandex_token  # заменить на SA key в prod
  secret_key = var.yandex_token

  # 152-ФЗ: автоудаление аудиозаписей через 90 дней
  lifecycle_rule {
    id      = "audio-ttl-90d"
    enabled = true

    filter {
      prefix = "audio/"
    }

    expiration {
      days = var.audio_retention_days
    }
  }

  # Хранение MLflow artifacts бессрочно
  lifecycle_rule {
    id      = "mlflow-keep"
    enabled = true

    filter {
      prefix = "mlflow/"
    }
  }

  # Версионирование для откатов модельных артефактов
  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "aws:kms"
      }
    }
  }
}

# ─────────────────────────────────────────────────────────────
# OUTPUTS
# ─────────────────────────────────────────────────────────────

output "vm_public_ip" {
  description = "Публичный IP VM — для деплоя и SSH"
  value       = yandex_compute_instance.speakup_vm.network_interface[0].nat_ip_address
}

output "matching_api_url" {
  description = "URL Matching API"
  value       = "http://${yandex_compute_instance.speakup_vm.network_interface[0].nat_ip_address}:8000"
}

output "grafana_url" {
  description = "URL Grafana Dashboard"
  value       = "http://${yandex_compute_instance.speakup_vm.network_interface[0].nat_ip_address}:3000"
}

output "mlflow_url" {
  description = "URL MLflow Tracking Server"
  value       = "http://${yandex_compute_instance.speakup_vm.network_interface[0].nat_ip_address}:5000"
}

output "airflow_url" {
  description = "URL Airflow Webserver"
  value       = "http://${yandex_compute_instance.speakup_vm.network_interface[0].nat_ip_address}:8080"
}

output "postgres_host" {
  description = "PostgreSQL host (Feature Store offline)"
  value       = yandex_mdb_postgresql_cluster.speakup_pg.host[0].fqdn
  sensitive   = false
}

output "redis_host" {
  description = "Redis host (Feature Store online)"
  value       = yandex_mdb_redis_cluster.speakup_redis.host[0].fqdn
  sensitive   = false
}

output "s3_bucket" {
  description = "Object Storage bucket name"
  value       = yandex_storage_bucket.speakup_artifacts.bucket
}

output "database_url" {
  description = "PostgreSQL connection string (для .env)"
  value       = "postgresql://${var.pg_user}:${var.pg_password}@${yandex_mdb_postgresql_cluster.speakup_pg.host[0].fqdn}:6432/${var.pg_database_name}"
  sensitive   = true
}
