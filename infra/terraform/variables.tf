# ─────────────────────────────────────────────────────────────
# variables.tf — входные параметры Terraform для SpeakUP
# ─────────────────────────────────────────────────────────────

# ── Общие ────────────────────────────────────────────────────

variable "project_name" {
  description = "Имя проекта (используется как префикс для всех ресурсов)"
  type        = string
  default     = "speakup-ml"
}

variable "environment" {
  description = "Окружение: dev | staging | prod"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment должен быть одним из: dev, staging, prod."
  }
}

variable "yandex_cloud_zone" {
  description = "Зона доступности Yandex Cloud"
  type        = string
  default     = "ru-central1-a"
}

variable "yandex_folder_id" {
  description = "ID каталога Yandex Cloud (берётся из env YC_FOLDER_ID)"
  type        = string
  sensitive   = true
}

variable "yandex_token" {
  description = "OAuth-токен Yandex Cloud (берётся из env YC_TOKEN)"
  type        = string
  sensitive   = true
}

# ── Compute (VM для MVP) ──────────────────────────────────────

variable "vm_cores" {
  description = "Количество vCPU для VM"
  type        = number
  default     = 2

  validation {
    condition     = var.vm_cores >= 2 && var.vm_cores <= 32
    error_message = "vm_cores должен быть от 2 до 32."
  }
}

variable "vm_memory_gb" {
  description = "Объём RAM в GB"
  type        = number
  default     = 4
}

variable "vm_disk_size_gb" {
  description = "Размер диска в GB"
  type        = number
  default     = 30
}

variable "vm_image_family" {
  description = "Семейство образа для VM"
  type        = string
  default     = "ubuntu-2204-lts"
}

variable "ssh_public_key_path" {
  description = "Путь к публичному SSH-ключу"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

# ── Network ───────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR блок для VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR блок для подсети"
  type        = string
  default     = "10.0.1.0/24"
}

# ── PostgreSQL (Managed) ──────────────────────────────────────

variable "pg_version" {
  description = "Версия PostgreSQL"
  type        = string
  default     = "15"
}

variable "pg_disk_size_gb" {
  description = "Размер диска PostgreSQL в GB"
  type        = number
  default     = 20
}

variable "pg_disk_type" {
  description = "Тип диска PostgreSQL: network-ssd | network-hdd"
  type        = string
  default     = "network-ssd"
}

variable "pg_resource_preset" {
  description = "Пресет ресурсов кластера: s2.micro | s2.small | s2.medium"
  type        = string
  default     = "s2.micro"
}

variable "pg_database_name" {
  description = "Имя базы данных"
  type        = string
  default     = "speakup"
}

variable "pg_user" {
  description = "Имя пользователя PostgreSQL"
  type        = string
  default     = "speakup_app"
  sensitive   = true
}

variable "pg_password" {
  description = "Пароль PostgreSQL (передавать через TF_VAR_pg_password)"
  type        = string
  sensitive   = true
}

# ── Redis (Managed) ───────────────────────────────────────────

variable "redis_version" {
  description = "Версия Redis"
  type        = string
  default     = "7.0"
}

variable "redis_resource_preset" {
  description = "Пресет ресурсов Redis"
  type        = string
  default     = "hm1.nano"
}

variable "redis_disk_size_gb" {
  description = "Размер диска Redis в GB"
  type        = number
  default     = 8
}

variable "redis_password" {
  description = "Пароль Redis (передавать через TF_VAR_redis_password)"
  type        = string
  sensitive   = true
}

# ── Object Storage (S3-совместимый) ──────────────────────────

variable "bucket_name" {
  description = "Имя бакета для хранения аудио и артефактов MLflow"
  type        = string
  default     = "speakup-ml-artifacts"
}

variable "audio_retention_days" {
  description = "TTL аудиозаписей в днях (152-ФЗ: удаление через 90 дней)"
  type        = number
  default     = 90
}

# ── Docker / Registry ─────────────────────────────────────────

variable "docker_image_tag" {
  description = "Тег Docker-образа matching-service для деплоя"
  type        = string
  default     = "latest"
}

variable "docker_registry" {
  description = "Docker registry (DockerHub username или CR URL)"
  type        = string
  default     = "YOUR_DOCKERHUB_USERNAME"
}

# ── Мониторинг ────────────────────────────────────────────────

variable "grafana_admin_password" {
  description = "Пароль администратора Grafana"
  type        = string
  sensitive   = true
  default     = "changeme_in_prod"
}

variable "alert_email" {
  description = "Email для получения алертов"
  type        = string
  default     = "ml-team@speakup.app"
}

# ── Теги (для всех ресурсов) ──────────────────────────────────

variable "common_tags" {
  description = "Общие теги для всех ресурсов"
  type        = map(string)
  default = {
    project     = "speakup-ml"
    environment = "prod"
    managed_by  = "terraform"
    team        = "ml-platform"
  }
}
