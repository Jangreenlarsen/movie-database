#!/bin/bash
# OTA-opdateringsscript for produktion — se DEPLOYMENT.md og ARCHITECTURE.md
# (feature #20). Dette er den reference-kopi der er tjekket ind i git; den
# FAKTISKE eksekverbare kopi ligger på serveren uden for git-working-tree'en
# (typisk /opt/moviedb-deploy.sh), så et `git pull` her aldrig overskriver
# den fil bash er ved at læse midt i kørslen. Efter en ændring af dette
# script skal den nye version manuelt kopieres derud igen — se DEPLOYMENT.md.
set -e

REPO_DIR="/opt/moviedb"

echo "[$(date -u +%FT%TZ)] Deploy startet"

cd "$REPO_DIR"
git pull origin main

cd "$REPO_DIR/backend"
.venv/bin/pip install --quiet -r requirements.txt
sudo /usr/bin/systemctl restart moviedb-backend

cd "$REPO_DIR/frontend"
npm install --silent
npm run build
sudo /usr/bin/systemctl reload caddy

echo "[$(date -u +%FT%TZ)] Deploy fuldført"
