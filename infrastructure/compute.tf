variable "tailscale_auth_key" {
  description = "Tailscale pre-auth key for unattended node registration"
  type        = string
  sensitive   = true
}

variable "infisical_encryption_key" {
  description = "Encryption key for Infisical self-hosted secrets (openssl rand -hex 32)"
  type        = string
  sensitive   = true
}

variable "infisical_auth_secret" {
  description = "Auth secret for Infisical API tokens (openssl rand -hex 32)"
  type        = string
  sensitive   = true
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key for instance access"
  type        = string
  default     = "../.ssh/toolset-oci.pub"
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

resource "oci_core_instance" "toolset" {
  compartment_id      = var.tenancy_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "toolset-server"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 2
    memory_in_gbs = 12
  }

  source_details {
    source_type             = "image"
    source_id               = "ocid1.image.oc1.sa-valparaiso-1.aaaaaaaabwwliv7irrkwvxq5ga5lqd5b6ape2cuauxz4knvechf4fwsvl23q"
    boot_volume_size_in_gbs = 100
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.toolset_subnet.id
    assign_public_ip = true
    display_name     = "toolset-vnic"
  }

  metadata = {
    ssh_authorized_keys = file(var.ssh_public_key_path)
    user_data           = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      tailscale_auth_key       = var.tailscale_auth_key
      infisical_encryption_key = var.infisical_encryption_key
      infisical_auth_secret    = var.infisical_auth_secret
    }))
  }

  preserve_boot_volume = true

  lifecycle {
    ignore_changes = [metadata]
  }
}

output "instance_public_ip" {
  description = "Public IP of the Toolset server (for Tailscale bootstrap only)"
  value       = oci_core_instance.toolset.public_ip
}

output "instance_display_name" {
  value = oci_core_instance.toolset.display_name
}
