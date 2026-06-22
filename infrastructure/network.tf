variable "tenancy_ocid" {
  default = "ocid1.tenancy.oc1..aaaaaaaa2brucpcafwsv5nnttqmpjyvaw55jyauxlchmjltd4b7epjlwio6q"
}

variable "region" {
  default = "sa-valparaiso-1"
}

# 1. Virtual Cloud Network (VCN)
resource "oci_core_vcn" "toolset_vcn" {
  compartment_id = var.tenancy_ocid
  display_name   = "toolset-vcn"
  cidr_block     = "10.0.0.0/16"
  dns_label      = "toolsetvcn"
}

# 2. Internet Gateway
resource "oci_core_internet_gateway" "toolset_ig" {
  compartment_id = var.tenancy_ocid
  vcn_id         = oci_core_vcn.toolset_vcn.id
  display_name   = "toolset-ig"
  enabled        = true
}

# 3. Default Route Table
resource "oci_core_default_route_table" "toolset_rt" {
  manage_default_resource_id = oci_core_vcn.toolset_vcn.default_route_table_id

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.toolset_ig.id
  }
}

# 4. Default Security List (Permitir SSH y Tailscale)
resource "oci_core_default_security_list" "toolset_sl" {
  manage_default_resource_id = oci_core_vcn.toolset_vcn.default_security_list_id

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    source   = "0.0.0.0/0"
    protocol = "6" # TCP
    tcp_options {
      max = 22
      min = 22
    }
  }

  ingress_security_rules {
    source   = "0.0.0.0/0"
    protocol = "17" # UDP (Tailscale)
    udp_options {
      max = 41641
      min = 41641
    }
  }
}

# 5. Subnet Pública
resource "oci_core_subnet" "toolset_subnet" {
  compartment_id      = var.tenancy_ocid
  vcn_id              = oci_core_vcn.toolset_vcn.id
  cidr_block          = "10.0.1.0/24"
  display_name        = "toolset-public-subnet"
  dns_label           = "toolsetsub"
  route_table_id      = oci_core_vcn.toolset_vcn.default_route_table_id
  security_list_ids   = [oci_core_vcn.toolset_vcn.default_security_list_id]
}
