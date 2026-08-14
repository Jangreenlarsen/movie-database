#!/bin/bash
# Feature #152 — provisionerer basissystemet i den genanvendelige VM-skabelon.
# Spejler DEPLOYMENT.md's "Sådan blev serveren sat op" (installations-log)
# trin 3-6+11 ordret, så skabelonen og den dokumenterede virkelighed aldrig
# kan drifte fra hinanden. Kører som root (Packers shell-provisioner kalder
# scriptet via sudo, se moviedb-appliance.pkr.hcl), derfor intet `sudo` her.
#
# BEVIDST UDELADT (se FEATURES.md #152 for begrundelsen): kloning af selve
# app-repoet (kræver en deploy key), backend/.env (kræver et rigtigt
# JWT_SECRET_KEY + TMDb-token), Caddyfile (afhænger af den endelige
# VM's hostname/IP), og aktivering af moviedb-backend (kræver alt
# ovenstående). De trin forbliver et kort, scriptet efterfølgende trin
# efter import — se DEPLOYMENT.md "Genanvendelig appliance-skabelon".
set -euo pipefail

echo "=== [1/6] Basis-pakker (DEPLOYMENT.md trin 3) ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git python3 python3-venv python3-pip curl gnupg ca-certificates ufw build-essential

echo "=== [2/6] MongoDB 8.0 (DEPLOYMENT.md trin 4) ==="
curl -fsSL https://pgp.mongodb.com/server-8.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-8.0.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg] https://repo.mongodb.org/apt/debian bookworm/mongodb-org/8.0 main" \
  > /etc/apt/sources.list.d/mongodb-org-8.0.list
apt-get update
apt-get install -y mongodb-org
systemctl enable --now mongod

echo "=== [3/6] Node.js 22 (DEPLOYMENT.md trin 5) ==="
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

echo "=== [4/6] Caddy 2 (DEPLOYMENT.md trin 6) ==="
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
apt-get update
apt-get install -y caddy

echo "=== [5/6] Firewall — kun 22/80/443 (DEPLOYMENT.md trin 11) ==="
ufw allow 22/tcp
ufw allow 443/tcp
ufw allow 80/tcp
ufw default deny incoming
ufw --force enable

echo "=== [6/6] Forbered app-mappe + stage (men aktivér ikke) systemd-units ==="
# /opt/moviedb oprettes tomt — selve `git clone` med deploy key er et
# bevidst efterfølgende, manuelt/scriptet trin (se DEPLOYMENT.md).
mkdir -p /opt/moviedb
chown jgl:jgl /opt/moviedb

# Unit-filerne er uploadet af Packers file-provisioner til /tmp forinden
# (se moviedb-appliance.pkr.hcl) — lægges på plads her, men moviedb-backend
# aktiveres bevidst IKKE: den vil fejle indtil appen er klonet og .env findes.
install -m 644 /tmp/packer-files/moviedb-backend.service /etc/systemd/system/moviedb-backend.service
install -m 644 /tmp/packer-files/moviedb-deploy-restart.path /etc/systemd/system/moviedb-deploy-restart.path
install -m 644 /tmp/packer-files/moviedb-deploy-restart.service /etc/systemd/system/moviedb-deploy-restart.service
install -m 644 /tmp/packer-files/moviedb-cert-install.path /etc/systemd/system/moviedb-cert-install.path
install -m 644 /tmp/packer-files/moviedb-cert-install.service /etc/systemd/system/moviedb-cert-install.service

# OTA-deploy og cert-install-scriptene bor bevidst uden for git-working-tree'en
# (se scripts/deploy.sh's egen kommentar — en samtidig "git pull" må aldrig
# kunne overskrive den fil bash er ved at eksekvere).
install -m 755 -o jgl -g jgl /tmp/packer-files/deploy.sh /opt/moviedb-deploy.sh
install -m 755 -o jgl -g jgl /tmp/packer-files/cert-install.sh /opt/moviedb-cert-install.sh
touch /opt/moviedb-deploy.log
chown jgl:jgl /opt/moviedb-deploy.log

systemctl daemon-reload
systemctl enable --now moviedb-deploy-restart.path
systemctl enable --now moviedb-cert-install.path

rm -rf /tmp/packer-files

echo "=== Provisionering fuldført ==="
