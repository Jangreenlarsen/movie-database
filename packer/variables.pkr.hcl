# Feature #152 — build-variabler for den genanvendelige VM-skabelon.
# Ingen af disse er hemmeligheder i sig selv (den offentlige SSH-nøgle er
# netop offentlig) — selve hemmeligheden (den private nøgle,
# moviedb_appliance_key uden .pub) rører aldrig denne fil og er gitignored.

variable "ssh_public_key_path" {
  type        = string
  default     = "moviedb_appliance_key.pub"
  description = "Offentlig SSH-nøgle der bages ind for jgl. Genereret med: ssh-keygen -t ed25519 -f moviedb_appliance_key -N \"\""
}

variable "vm_name" {
  type    = string
  default = "moviedb-appliance"
}

variable "cpus" {
  type    = number
  default = 2
}

variable "memory_mb" {
  type    = number
  default = 2048
}

variable "disk_size_mb" {
  type    = number
  default = 20480
}

variable "iso_url" {
  type    = string
  default = "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.6.0-amd64-netinst.iso"
}

# Packers "file:"-checksum henter og matcher automatisk mod Debians egen
# publicerede SHA256SUMS-fil frem for at vi skal opdatere et hardkodet hash
# ved hver Debian-point-release.
variable "iso_checksum" {
  type    = string
  default = "file:https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/SHA256SUMS"
}
