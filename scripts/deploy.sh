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

# Feature #194 — Jan: "vi skal have en mulighed for at opdater fra github på
# Main eller Dev på portal". Branchen sendes som script'ets eneste argument
# (backend/app/services/deploy_service.py), valideret opstrøms som et
# Pydantic Literal (main.py's DeployRequest) — men scriptet validerer også
# selv, defensivt, i tilfælde af et direkte/manuelt kald.
BRANCH="${1:-main}"
case "$BRANCH" in
  main|dev) ;;
  *)
    echo "[$(date -u +%FT%TZ)] Ugyldig branch: '$BRANCH' (kun main/dev understøttet)" >&2
    exit 1
    ;;
esac

echo "[$(date -u +%FT%TZ)] Deploy startet (branch: $BRANCH)"

cd "$REPO_DIR"
BEFORE_COMMIT=$(git rev-parse HEAD)
git fetch origin "$BRANCH"

# Skift til branchen hvis den ikke allerede er den aktive — dev findes
# typisk kun som origin/dev ved første skift (den oprindelige kloning fulgte
# kun main, jf. DEPLOYMENT.md), så en lokal sporings-branch oprettes da.
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH" "origin/$BRANCH"
fi
git merge --ff-only "origin/$BRANCH"
AFTER_COMMIT=$(git rev-parse HEAD)

# BUGS.md #36 — intet nyt at hente er ikke en fejl: spring den fulde
# pipeline (pip/npm/restart) helt over i stedet for at genstarte unødigt,
# og skriv et tydeligt udfald frontend kan skelne fra en reel fejl.
if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
  printf '{"outcome":"up-to-date","branch":"%s","commit":"%s","at":"%s"}\n' "$BRANCH" "$AFTER_COMMIT" "$(date -u +%FT%TZ)" > "$STATUS_FILE"
  echo "[$(date -u +%FT%TZ)] Allerede opdateret — intet nyt at hente (branch $BRANCH, commit $AFTER_COMMIT)"
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

printf '{"outcome":"updated","branch":"%s","commit":"%s","at":"%s"}\n' "$BRANCH" "$AFTER_COMMIT" "$(date -u +%FT%TZ)" > "$STATUS_FILE"
echo "[$(date -u +%FT%TZ)] Deploy fuldført (branch: $BRANCH, genstart udløst)"
