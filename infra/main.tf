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

  # REQUIREMENT: the public only ever reaches Caddy, never the app. Port 8000 is
  # deliberately absent here and the container binds to 127.0.0.1, so there is no
  # way to skip the password prompt by hitting the app port directly.
  ingress {
    description = "HTTP - redirects to HTTPS and answers ACME certificate challenges"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
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

  # REQUIREMENT: 2 GB is not enough room for two container images. The original
  # volume ran to 98% full, which would have taken the demo down on its own.
  # 30 GB is both the minimum this AMI's snapshot allows and the free tier limit.
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  # REQUIREMENT: user_data only ever runs on a first boot, so editing the script
  # below has no effect unless the instance is replaced. This makes that explicit
  # rather than leaving a change that silently does nothing.
  user_data_replace_on_change = true

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

    # Bound to 127.0.0.1 on purpose: the app is reachable only from inside the
    # box, so every request from outside has to pass through Caddy's password
    # prompt first.
    docker run -d --restart unless-stopped --name flcs \
      -p 127.0.0.1:8000:8000 --env-file .env flcs

    # Caddy fetches and renews the Let's Encrypt certificate on its own, checks
    # the password, then forwards to the app. The quoted heredoc matters - the
    # bcrypt hash contains dollar signs the shell would otherwise mangle.
    mkdir -p /etc/caddy
    cat > /etc/caddy/Caddyfile <<'CADDYFILE'
    ${var.domain} {
        basic_auth {
            ${var.basic_auth_user} ${var.basic_auth_hash}
        }
        reverse_proxy 127.0.0.1:8000
    }
    CADDYFILE

    # Host networking so Caddy can bind 80 and 443 and still reach the app on
    # localhost. The named volume keeps the certificate across restarts, which
    # matters because Let's Encrypt rate-limits repeat requests.
    docker run -d --restart unless-stopped --name caddy --network host \
      -v /etc/caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
      -v caddy_data:/data \
      -v caddy_config:/config \
      caddy:2
  EOF

  tags = { Name = "flcs-demo" }

  # REQUIREMENT: do not rebuild the box just because Amazon published a newer
  # AL2023 image. Without this, every apply destroys the running demo and the
  # public link goes dead for several minutes. Change the AMI deliberately, by
  # tainting the instance, not as a side effect of an unrelated change.
  lifecycle {
    ignore_changes = [ami]
  }
}

# REQUIREMENT: a fixed public address. Without it the IP changes every time the
# instance stops and starts, which breaks DNS and any link already handed out.
resource "aws_eip" "flcs" {
  instance = aws_instance.flcs.id
  domain   = "vpc"
}

output "app_url" {
  value = "https://${var.domain}"
}

output "ssh" {
  value = "ssh -i infra/flcs-key.pem ec2-user@${aws_eip.flcs.public_ip}"
}