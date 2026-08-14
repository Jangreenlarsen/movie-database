# Feature #152 — genanvendelig Debian 13-appliance til import i Synology
# Virtual Machine Manager (og enhver anden hypervisor der forstår .ova).
# Bygges 100% lokalt/uafhængigt via VirtualBox — ingen forbindelse til den
# kørende produktions-VM (10.1.130.10) på noget tidspunkt. Se
# DEPLOYMENT.md "Genanvendelig appliance-skabelon" for build-kommando og
# den efterfølgende, manuelle finish-opsætning (klon repo, .env, Caddyfile).

packer {
  required_plugins {
    virtualbox = {
      source  = "github.com/hashicorp/virtualbox"
      version = ">= 1.0.0"
    }
  }
}

source "virtualbox-iso" "moviedb" {
  vm_name          = var.vm_name
  guest_os_type    = "Debian_64"
  iso_url          = var.iso_url
  iso_checksum     = var.iso_checksum
  cpus             = var.cpus
  memory           = var.memory_mb
  disk_size        = var.disk_size_mb
  hard_drive_interface = "sata"
  headless         = true
  format           = "ova"
  output_directory = "output"

  http_directory = "http"
  boot_wait      = "5s"
  boot_command = [
    "<esc><wait>",
    "install ",
    "auto=true ",
    "priority=critical ",
    "preseed/url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg ",
    "interface=auto ",
    "hostname=moviedb-appliance ",
    "domain=unassigned-domain ",
    "<enter>"
  ]

  ssh_username           = "jgl"
  ssh_password           = var.jgl_password
  ssh_timeout            = "40m"
  shutdown_command       = "sudo shutdown -P now"
  shutdown_timeout       = "5m"

  guest_additions_mode = "disable"
  vboxmanage = [
    ["modifyvm", "{{ .Name }}", "--nictype1", "virtio"]
  ]
}

build {
  sources = ["source.virtualbox-iso.moviedb"]

  provisioner "file" {
    source      = "../scripts"
    destination = "/tmp/packer-files"
  }

  provisioner "shell" {
    script = "provision.sh"
    # jgl har (bevidst, se preseed.cfg) ingen NOPASSWD-sudo-regel før
    # provision.sh selv opretter den (trin 6) — reglen kan derfor ikke
    # forudsættes for dette allerførste sudo-kald. Adgangskoden sendes ind
    # via stdin til `sudo -S` i stedet; resten af scriptet kører videre i
    # samme allerede-eskalerede proces, uanset om sudoers-filen findes.
    execute_command = "echo '${var.jgl_password}' | sudo -S -p '' sh -c 'chmod +x {{ .Path }} && {{ .Path }}'"
  }
}
