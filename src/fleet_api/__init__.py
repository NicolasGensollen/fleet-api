"""fleet-api — mini-service de supervision d'une flotte de robots.

Support du module « Usine Logicielle et CI/CD », ESIA A3.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fleet-api")
except PackageNotFoundError:  # exécuté depuis les sources, non installé
    __version__ = "0.0.0+dev"
