terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }
}

provider "oci" {
  region = "sa-valparaiso-1"
  # Las credenciales ahora se leen automáticamente de ~/.oci/config
  # En local: Usa la llave API que configuramos.
  # En GitHub Actions: Usa el Workload Identity Token inyectado por oracle-actions.
}

data "oci_identity_domains" "default" {
  compartment_id = "ocid1.tenancy.oc1..aaaaaaaa2brucpcafwsv5nnttqmpjyvaw55jyauxlchmjltd4b7epjlwio6q"
  display_name   = "Default"
}
