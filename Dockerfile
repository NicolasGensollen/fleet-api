# syntax=docker/dockerfile:1
# ============================================================================
# Image de production de fleet-api.
#
#   docker build -t fleet-api:latest .
#
# Trois principes, dans l'ordre d'importance :
#   1. Les dépendances s'installent AVANT que le code source n'entre dans
#      l'image. Une modification de `src/` n'invalide donc jamais la couche
#      d'installation.
#   2. La chaîne de construction (uv, compilateurs, caches) reste dans le
#      premier étage. Seul l'environnement virtuel franchit la frontière.
#   3. Le conteneur ne tourne pas en root.
# ============================================================================

######################  Étage 1 — construction  ##############################
FROM python:3.14-slim-trixie AS builder

# uv épinglé : en production, préférer un digest sha256.
COPY --from=ghcr.io/astral-sh/uv:0.12.6 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_DEV=1

WORKDIR /app

# (1) Les dépendances seules.
#     Les deux fichiers sont montés le temps de la commande — ils n'entrent pas
#     dans la couche. Celle-ci n'est invalidée que si uv.lock change.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# (2) Le code, puis le projet lui-même — quelques millisecondes.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

######################  Étage 2 — exécution  #################################
FROM python:3.14-slim-trixie

# Utilisateur système à UID numérique fixe : Kubernetes vérifie l'UID, pas le nom.
RUN groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Seul l'environnement virtuel traverse : ni uv, ni cache, ni outils de build.
# Le --chown évite un RUN chown -R qui dupliquerait toute la couche.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src   /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# UID:GID numériques plutôt que le nom : c'est sous cette forme que Kubernetes
# sait vérifier `runAsNonRoot`.
USER 10001:10001
EXPOSE 8000

# Pas besoin d'installer curl : urllib fait l'affaire et n'ajoute
# ni paquet ni surface d'attaque.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", \
       "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"]

CMD ["fastapi", "run", "src/fleet_api/api.py", "--host", "0.0.0.0", "--port", "8000"]
