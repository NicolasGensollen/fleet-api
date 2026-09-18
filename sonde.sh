#!/usr/bin/env bash
# Sonde le service à intervalle régulier et journalise le code HTTP.
#
#   ./sonde.sh > sonde.log &      # lancer AVANT la bascule
#   ./bascule.sh green            # basculer
#   kill %1                       # arrêter la sonde
#   ./analyse.sh sonde.log        # compter l'interruption
#
# Limite assumée de la méthode : une requête toutes les 100 ms et une seule
# connexion à la fois. La résolution est donc de 100 ms, et une coupure plus
# courte peut passer inaperçue. C'est exactement le genre de limite qu'il faut
# savoir énoncer quand on présente une mesure.

set -uo pipefail

URL="${1:-http://localhost:8080/version}"
INTERVALLE="${2:-0.1}"

while true; do
  DEBUT=$(date +%s.%N)
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$URL" || echo "000")
  echo "$DEBUT $CODE"
  sleep "$INTERVALLE"
done
