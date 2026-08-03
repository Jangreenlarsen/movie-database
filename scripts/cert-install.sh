#!/bin/bash
# Installerer et staged TLS-certifikat (feature #73) — kaldes af
# moviedb-cert-install.service (root, uden for moviedb-backend's sandkasse),
# udløst af backend'ens trigger-fil. Se ARCHITECTURE.md/DEPLOYMENT.md.
set -uo pipefail

STAGING_DIR="/opt/moviedb/certs/pending"
LIVE_DIR="/etc/caddy/certs"
CN="movie.ll.lan"
TRIGGER="/opt/moviedb/.cert-install-trigger"

trap 'rm -f "$TRIGGER"' EXIT

if [ ! -f "$STAGING_DIR/cert.pem" ] || [ ! -f "$STAGING_DIR/key.pem" ]; then
  echo "Intet staged certifikat fundet i $STAGING_DIR — afbryder."
  exit 1
fi

# Backup af det nuværende certifikat/nøgle, så en fejlslagen installation kan
# rulles tilbage med en simpel fil-kopi over SSH uden at skulle generere noget forfra.
[ -f "$LIVE_DIR/$CN.crt" ] && cp -p "$LIVE_DIR/$CN.crt" "$LIVE_DIR/$CN.crt.bak"
[ -f "$LIVE_DIR/$CN.key" ] && cp -p "$LIVE_DIR/$CN.key" "$LIVE_DIR/$CN.key.bak"

cp "$STAGING_DIR/cert.pem" "$LIVE_DIR/$CN.crt"
cp "$STAGING_DIR/key.pem" "$LIVE_DIR/$CN.key"
chown root:caddy "$LIVE_DIR/$CN.crt" "$LIVE_DIR/$CN.key"
chmod 640 "$LIVE_DIR/$CN.crt" "$LIVE_DIR/$CN.key"

if ! caddy validate --config /etc/caddy/Caddyfile; then
  echo "Caddy-config ugyldig efter cert-installation — .bak-filer i $LIVE_DIR kan bruges til at rulle tilbage." >&2
  exit 1
fi

systemctl reload caddy
rm -f "$STAGING_DIR/cert.pem" "$STAGING_DIR/key.pem"
