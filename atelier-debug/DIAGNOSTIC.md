# DIAGNOSTIC.md — atelier de débogage

## Panne 1 — Tests

**Symptôme :** Une PR qui ne modifie que des tests reste bloquée sur « Expected — Waiting for status to be reported », et aucun run n'apparaît dans l'onglet Actions.

**Cause :** Le workflow ne se déclenche jamais sur cette PR, pour deux raisons cumulées. D'abord, `branches: [master]` sous `pull_request` filtre la branche cible de la PR, pas la branche source ; or la branche par défaut du dépôt est main, donc aucune PR ne cible master et le filtre exclut tout. Ensuite, même une fois master corrigé en main, le filtre `paths: ['src/**']` exclut une PR qui ne touche que des tests. Comme tests est déclaré statut requis, la règle de protection attend indéfiniment un résultat qui n'arrivera jamais : le statut n'est pas en échec, il est absent.

**Correction**

```diff
 on:
   push:
     branches: [main]
   pull_request:
-    branches: [master]
-    paths:
-      - 'src/**'
```
