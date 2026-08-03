#!/bin/bash
# OTA-opdateringsscript for produktion — se DEPLOYMENT.md og ARCHITECTURE.md
# (feature #20). Dette er den reference-kopi der er tjekket ind i git; den
# FAKTISKE eksekverbare kopi ligger på serveren uden for git-working-tree'en
# (typisk /opt/moviedb-deploy.sh), så et `git pull` her aldrig overskriver
# den fil bash er ved at læse midt i kørslen. Efter en ændring af dette
# script skal den nye version manuelt kopieres derud igen — se DEPLOYMENT.md.
#
# Kører som en detached child af moviedb-backend-servicen, som har
# NoNewPrivileges=true — det gør `sudo` permanent ubrugeligt her (systemd
# blokerer al ny-privilegie-optjening for hele process-træet, uanset
# sudoers-opsætning). Genstart af services sker derfor IKKE via sudo, men
# ved at røre en trigger-fil som en separat, ikke-sandboxed systemd
# path-unit (moviedb-deploy-restart.path, kører som root) reagerer på.
set -e

REPO_DIR="/opt/moviedb"
RESTART_TRIGGER="$REPO_DIR/.deploy-restart-trigger"
STATUS_FILE="$REPO_DIR/.deploy-status"

echo "[$(date -u +%FT%TZ)] Deploy startet"

cd "$REPO_DIR"
BEFORE_COMMIT=$(git rev-parse HEAD)
git pull origin main
AFTER_COMMIT=$(git rev-parse HEAD)

# BUGS.md #36 — intet nyt at hente er ikke en fejl: spring den fulde
# pipeline (pip/npm/restart) helt over i stedet for at genstarte unødigt,
# og skriv et tydeligt udfald frontend kan skelne fra en reel fejl.
if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
  printf '{"outcome":"up-to-date","commit":"%s","at":"%s"}\n' "$AFTER_COMMIT" "$(date -u +%FT%TZ)" > "$STATUS_FILE"
  echo "[$(date -u +%FT%TZ)] Allerede opdateret — intet nyt at hente (commit $AFTER_COMMIT)"
  exit 0
fi

cd "$REPO_DIR/backend"
.venv/bin/pip install --quiet -r requirements.txt

cd "$REPO_DIR/frontend"
npm install --silent
npm run build

# Fjern evt. efterladt trigger-fil først, så touch nedenfor altid er en
# frisk "begynder at eksistere"-overgang for path-unitten (PathExists=
# aktiverer kun ved den overgang, ikke løbende mens filen findes).
rm -f "$RESTART_TRIGGER"
touch "$RESTART_TRIGGER"

printf '{"outcome":"updated","commit":"%s","at":"%s"}\n' "$AFTER_COMMIT" "$(date -u +%FT%TZ)" > "$STATUS_FILE"
echo "[$(date -u +%FT%TZ)] Deploy fuldført (genstart udløst)"
