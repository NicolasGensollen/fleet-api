#!/usr/bin/env bash
# Analyse un journal produit par sonde.sh et estime l'interruption de service.
#
#   ./analyse.sh sonde.log

set -euo pipefail
JOURNAL="${1:-sonde.log}"
INTERVALLE_MS="${2:-100}"

TOTAL=$(wc -l < "$JOURNAL")
ECHECS=$(awk '$2 != "200"' "$JOURNAL" | wc -l)
SUCCES=$((TOTAL - ECHECS))

echo "Requêtes         : $TOTAL"
echo "Succès (200)     : $SUCCES"
echo "Échecs           : $ECHECS"
if [[ "$TOTAL" -gt 0 ]]; then
  awk -v s="$SUCCES" -v t="$TOTAL" 'BEGIN { printf "Taux de succès   : %.2f %%\n", 100*s/t }'
fi
echo "Interruption ≈   : $((ECHECS * INTERVALLE_MS)) ms  (± $INTERVALLE_MS ms)"

if [[ "$ECHECS" -gt 0 ]]; then
  echo
  echo "Codes rencontrés :"
  awk '{print $2}' "$JOURNAL" | sort | uniq -c | sort -rn
fi
