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

---

## Panne 2 — Build et vérification

**Symptôme :** La tâche build est verte et affiche bien le contenu de `dist/` dans ses logs, mais la tâche verifier échoue systématiquement avec ls: cannot access 'dist/': No such file or directory.

**Cause :** `needs: build` impose un ordre d'exécution, pas un disque partagé. Les deux tâches s'exécutent sur deux machines virtuelles distinctes, créées puis détruites indépendamment. Le dossier `dist/` produit par build a disparu avec sa machine ; verifier démarre sur une machine neuve et vide, qui n'a même pas fait de checkout. Pour qu'un fichier passe d'une tâche à l'autre, il faut le publier en artefact.

**Correction**

```diff
       - name: Construire la distribution
         run: |
           uv build
           echo "Contenu de dist/ :"
           ls -la dist/
+
+      - uses: actions/upload-artifact@v7
+        with:
+          name: distribution
+          path: dist/

   verifier:
     runs-on: ubuntu-latest
     needs: build
     steps:
+      - uses: actions/download-artifact@v8
+        with:
+          name: distribution
+          path: dist/
+
       - name: Vérifier que la distribution existe
```

*Attention aux versions : upload-artifact est en v7 et download-artifact en v8. Écrire la même des deux côtés par symétrie produit une erreur de résolution.*

---

## Panne 3 — Couverture

**Symptôme :** Les tests passent et la couverture est calculée, mais la dernière étape échoue avec gh: Resource not accessible by integration (HTTP 403) au moment de publier le commentaire sur la pull request.

**Cause :** Le jeton n'est ni absent ni expiré : il est sous-privilégié. Le dépôt est configuré avec les permissions de workflow par défaut en lecture seule — le réglage recommandé — et le workflow ne déclare aucun bloc permissions:. Le `GITHUB_TOKEN` fourni au run n'a donc pas le droit d'écrire sur les pull requests, et l'appel `gh pr comment` est refusé. Le message d'erreur ne le suggère pas : rien dans « Resource not accessible by integration » ne pointe vers un bloc permissions: manquant.

**Correction**

```diff
 jobs:
   couverture:
     runs-on: ubuntu-latest
+    permissions:
+      contents: read
+      pull-requests: write
     steps:
```
