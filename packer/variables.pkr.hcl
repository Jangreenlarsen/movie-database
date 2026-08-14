# Feature #152 — build-variabler for den genanvendelige VM-skabelon.
#
# Jans valg (2026-08-14, efter første forsøg): almindeligt bruger/adgangskode-
# login i stedet for SSH-nøgle-only — konsol-login i VMM skal virke uden en
# nøglefil. Adgangskoden nedenfor er en bevidst simpel bootstrap-værdi: den
# er UBRUGELIG efter første login, fordi provision.sh sætter kontoen til at
# skulle skiftes med det samme (`chage -d 0`) — samme mønster som CLAUDE.md
# regel 16 kræver for usikre standardværdier.

variable "jgl_password" {
  type        = string
  default     = "ChangeMe123!"
  description = "Bootstrap-adgangskode for jgl. Bruges også af Packer selv til at forbinde under build. SKAL skiftes ved første login — håndhæves automatisk (chage -d 0), ikke kun en anbefaling."
  sensitive   = true
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
