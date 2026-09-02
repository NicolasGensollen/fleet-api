"""Stockage de la télémétrie.

Deux implémentations derrière la même interface :

* `MemoryStore` — en mémoire, utilisée par défaut et dans les tests unitaires.
  Aucune dépendance externe : la suite de tests tourne sans base de données.
* `PostgresStore` — utilisée dès que la variable d'environnement `DATABASE_URL`
  est définie. C'est elle que testent les tests d'intégration de la séance 5.

Cette séparation n'est pas cosmétique : elle permet de tester la logique de
l'API sans infrastructure, et de réserver la base de données aux tests qui la
concernent réellement.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from fleet_api.models import Position, Reading


class Store(ABC):
    """Interface de stockage de la télémétrie."""

    @abstractmethod
    def add(self, reading: Reading) -> None:
        """Enregistre une mesure."""

    @abstractmethod
    def latest(self, robot_id: str) -> Reading | None:
        """Renvoie la dernière mesure connue d'un robot, ou None."""

    @abstractmethod
    def latest_all(self) -> list[Reading]:
        """Renvoie la dernière mesure de chaque robot connu."""

    @abstractmethod
    def history(self, robot_id: str, limit: int = 100) -> list[Reading]:
        """Renvoie les mesures d'un robot, de la plus récente à la plus ancienne."""

    @abstractmethod
    def ping(self) -> bool:
        """Vérifie que le stockage répond. Utilisé par /health."""


class MemoryStore(Store):
    """Stockage en mémoire. Perd tout au redémarrage — c'est voulu."""

    def __init__(self) -> None:
        self._readings: list[Reading] = []

    def add(self, reading: Reading) -> None:
        self._readings.append(reading)

    def latest(self, robot_id: str) -> Reading | None:
        mesures = [r for r in self._readings if r.robot_id == robot_id]
        return max(mesures, key=lambda r: r.timestamp_s) if mesures else None

    def latest_all(self) -> list[Reading]:
        par_robot: dict[str, Reading] = {}
        for r in self._readings:
            connue = par_robot.get(r.robot_id)
            if connue is None or r.timestamp_s > connue.timestamp_s:
                par_robot[r.robot_id] = r
        return list(par_robot.values())

    def history(self, robot_id: str, limit: int = 100) -> list[Reading]:
        mesures = [r for r in self._readings if r.robot_id == robot_id]
        mesures.sort(key=lambda r: r.timestamp_s, reverse=True)
        return mesures[:limit]

    def ping(self) -> bool:
        return True


SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    TEXT             NOT NULL,
    timestamp_s DOUBLE PRECISION NOT NULL,
    voltage_mv  INTEGER          NOT NULL,
    pos_x       DOUBLE PRECISION NOT NULL,
    pos_y       DOUBLE PRECISION NOT NULL,
    is_charging BOOLEAN          NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS readings_robot_ts
    ON readings (robot_id, timestamp_s DESC);
"""


class PostgresStore(Store):
    """Stockage PostgreSQL.

    Volontairement écrit en SQL brut plutôt qu'avec un ORM : le sujet du module
    est la chaîne de construction, pas la couche de persistance.
    """

    def __init__(self, dsn: str) -> None:
        import psycopg  # import local : la dépendance n'est requise que ici

        self._connect = lambda: psycopg.connect(dsn)
        with self._connect() as conn:
            conn.execute(SCHEMA)

    @staticmethod
    def _to_reading(row: tuple) -> Reading:
        robot_id, timestamp_s, voltage_mv, x, y, is_charging = row
        return Reading(
            robot_id=robot_id,
            timestamp_s=timestamp_s,
            voltage_mv=voltage_mv,
            position=Position(x=x, y=y),
            is_charging=is_charging,
        )

    _SELECT = (
        "SELECT robot_id, timestamp_s, voltage_mv, pos_x, pos_y, is_charging "
        "FROM readings"
    )

    def add(self, reading: Reading) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO readings "
                "(robot_id, timestamp_s, voltage_mv, pos_x, pos_y, is_charging) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    reading.robot_id,
                    reading.timestamp_s,
                    reading.voltage_mv,
                    reading.position.x,
                    reading.position.y,
                    reading.is_charging,
                ),
            )

    def latest(self, robot_id: str) -> Reading | None:
        with self._connect() as conn:
            row = conn.execute(
                f"{self._SELECT} WHERE robot_id = %s ORDER BY timestamp_s DESC LIMIT 1",
                (robot_id,),
            ).fetchone()
        return self._to_reading(row) if row else None

    def latest_all(self) -> list[Reading]:
        with self._connect() as conn:
            rows = conn.execute(
                f"{self._SELECT} WHERE (robot_id, timestamp_s) IN "
                "(SELECT robot_id, MAX(timestamp_s) FROM readings GROUP BY robot_id)"
            ).fetchall()
        return [self._to_reading(r) for r in rows]

    def history(self, robot_id: str, limit: int = 100) -> list[Reading]:
        with self._connect() as conn:
            rows = conn.execute(
                f"{self._SELECT} WHERE robot_id = %s "
                "ORDER BY timestamp_s DESC LIMIT %s",
                (robot_id, limit),
            ).fetchall()
        return [self._to_reading(r) for r in rows]

    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False


def build_store() -> Store:
    """Choisit l'implémentation selon l'environnement.

    Sans `DATABASE_URL`, on tourne en mémoire — c'est le cas en développement et
    dans les tests unitaires. Avec, on parle à PostgreSQL.
    """
    dsn = os.environ.get("DATABASE_URL")
    return PostgresStore(dsn) if dsn else MemoryStore()
