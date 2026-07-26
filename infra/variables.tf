# The knobs. Actual values live in terraform.tfvars, which is gitignored.

variable "region" {
  default = "us-east-1"
}

variable "repo_url" {
  description = "Public HTTPS clone URL of the flcs repo"
}

variable "ssh_cidr" {
  description = "Who may SSH in. Narrow this to your own IP/32 if you care."
  default     = "0.0.0.0/0"
}

variable "anthropic_api_key" {
  sensitive = true
}

variable "servicenow_url" {}

variable "servicenow_user" {}

variable "servicenow_password" {
  sensitive = true
}