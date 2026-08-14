#!/bin/sh
# Feature #152 — init-velkomstrutine ved allerførste login (konsol ELLER SSH)
# på den genanvendelige appliance-skabelon. Lægges i /etc/profile.d/, som
# /etc/profile kilder ved enhver login-shell — markørfilen i $HOME sikrer at
# den kun vises én gang pr. bruger, uanset login-metode.
#
# Viser bl.a. den DHCP-tildelte IP — det konkrete problem der udløste denne
# rutine (Jan kunne ikke finde VM'ens IP efter import, da konsol-login uden
# denne rutine ikke viser andet end et login-prompt).

MARKER="$HOME/.moviedb_first_login_done"

if [ ! -f "$MARKER" ]; then
  cat <<'BANNER'

========================================================
 Velkommen til Movie Database-appliance'n (FEATURES.md #152)
========================================================

Netværk:
BANNER
  echo "  hostname: $(hostname)"
  ip -4 -o addr show scope global 2>/dev/null | awk '{print "  " $2 ": " $4}'

  cat <<'BANNER'

Adgangskoden skal skiftes ved dette login (systemet beder om det
automatisk før du når hertil — det er ikke valgfrit).

Næste skridt (fuld vejledning: DEPLOYMENT.md i moviedb-repoet,
afsnittet "Genanvendelig appliance-skabelon"):
  1. git clone <deploy-key-URL> /opt/moviedb
  2. Opret backend/.env (frisk JWT_SECRET_KEY, TMDb-token, COOKIE_SECURE=true)
  3. cd frontend && npm install && npm run build
  4. sudo systemctl enable --now moviedb-backend caddy

========================================================

BANNER
  touch "$MARKER"
fi
