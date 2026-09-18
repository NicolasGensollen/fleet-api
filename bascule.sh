#!/usr/bin/env bash
# Bascule le trafic vers la couleur demandée, sans redémarrer le proxy.
#
#   ./bascule.sh green
#   ./bascule.sh blue
#
# `caddy reload` recharge la configuration à chaud : le processus n'est pas
# redémarré, les connexions en cours ne sont pas coupées.

set -euo pipefail

COULEUR="${1:-}"
if [[ "$COULEUR" != "blue" && "$COULEUR" != "green" ]]; then
  echo "usage: $0 {blue|green}" >&2
  exit 1
fi

echo "→ bascule vers $COULEUR"
docker compose -f compose.bluegreen.yaml exec -T proxy \
  caddy reload --config "/etc/caddy/Caddyfile.$COULEUR"

echo "→ vérification"
curl -sS http://localhost:8080/version
echo
