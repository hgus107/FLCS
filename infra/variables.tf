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

# The hostname Caddy requests a certificate for. It must already resolve to this
# instance's Elastic IP before the box boots, or the certificate request fails.
variable "domain" {
  description = "Public hostname served over HTTPS"
}

variable "basic_auth_user" {
  description = "Username for the password prompt in front of the demo"
  default     = "demo"
}

# A bcrypt hash, not the password. Generated with:
#   htpasswd -bnBC 12 "" 'the-password' | tr -d ':\n'
variable "basic_auth_hash" {
  description = "Bcrypt hash of the demo password"
  sensitive   = true
}