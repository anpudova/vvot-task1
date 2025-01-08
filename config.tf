terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

variable "folder_id" {
  type = string
  description = "ID каталога Yandex Cloud"
}

variable "cloud_id" {
  type = string
  description = "ID облака Yandex Cloud"
}

variable "zone" {
  type = string
}

variable "telegram_bot_token" {
  type = string
  description = "Токен Telegram-бота"
}

variable "webhook_url" {
  type = string
  description = "URL webhook"
}

provider "yandex" {
    service_account_key_file = "my-key.json"
    cloud_id = var.cloud_id
    folder_id = var.folder_id
    zone = var.zone
}

provider "null" {}

resource "null_resource" "register_webhook" {
  provisioner "local-exec" {
    when = create
    command = <<EOT
curl -X POST https://api.telegram.org/bot${var.telegram_bot_token}/setWebhook?url=${var.webhook_url}
EOT
  }
}

resource "null_resource" "delete_webhook" {
  provisioner "local-exec" {
    when = destroy
    command = <<EOT
curl -X POST https://api.telegram.org/bot${var.telegram_bot_token}/deleteWebhook
EOT
  }
}

resource "yandex_storage_object" "test-object" {
  bucket     = "my-gpt-instructions"
  key        = "instruction.json"
  source     = "instruction.json"
}
