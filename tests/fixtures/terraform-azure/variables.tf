variable "subscription_id" {
  type        = string
  description = "Azure subscription to deploy into."
}

variable "environment" {
  type = string
}

variable "location" {
  type    = string
  default = "westeurope"
}
