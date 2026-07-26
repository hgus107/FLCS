# INFRASTRUCTURE: builds the whole demo environment in one command — a keypair, a
# firewall rule, and one small EC2 box that installs Docker, clones the repo,
# builds the image and starts the app. `terraform destroy` removes all of it.

terraform {
  required_providers {
    aws   = { source = "hashicorp/aws", version = "~> 5.0" }
    tls   = { source = "hashicorp/tls", version = "~> 4.0" }
    local = { source = "hashicorp/local", version = "~> 2.0" }
  }
}

provider "aws" {
  region = var.region
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# REQUIREMENT: generate the SSH key here so there is no manual console step.
# The .pem lands in infra/ and is gitignored.
resource "tls_private_key" "flcs" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "flcs" {
  key_name   = "flcs-key"
  public_key = tls_private_key.flcs.public_key_openssh
}

resource "local_file" "pem" {
  content         = tls_private_key.flcs.private_key_pem
  filename        = "${path.module}/flcs-key.pem"
  file_permission = "0400"
}

resource "aws_security_group" "flcs" {
  name        = "flcs-sg"
  description = "FLCS demo: SSH plus the app port"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }

  ingress {
    description = "App"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "flcs" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t3.micro"
  key_name               = aws_key_pair.flcs.key_name
  vpc_security_group_ids = [aws_security_group.flcs.id]

  # REQUIREMENT: runs once on first boot. Secrets are written to .env inside the
  # box rather than baked into the image.
  user_data = <<-EOF
    #!/bin/bash
    set -eux
    dnf install -y docker git
    systemctl enable --now docker

    cd /home/ec2-user
    git clone ${var.repo_url} flcs
    cd flcs

    printf 'ANTHROPIC_API_KEY=%s\n'   '${var.anthropic_api_key}'   >  .env
    printf 'SERVICENOW_URL=%s\n'      '${var.servicenow_url}'      >> .env
    printf 'SERVICENOW_USER=%s\n'     '${var.servicenow_user}'     >> .env
    printf 'SERVICENOW_PASSWORD=%s\n' '${var.servicenow_password}' >> .env

    docker build -t flcs .
    docker run -d --restart unless-stopped -p 8000:8000 --env-file .env flcs
  EOF

  tags = { Name = "flcs-demo" }
}

output "app_url" {
  value = "http://${aws_instance.flcs.public_ip}:8000"
}

output "ssh" {
  value = "ssh -i infra/flcs-key.pem ec2-user@${aws_instance.flcs.public_ip}"
}