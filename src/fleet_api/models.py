"""Types de données du service de supervision de flotte."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RobotState(StrEnum):
    """État opérationnel d'un robot, du plus au moins critique."""

    OFFLINE = "offline"
    """Aucune télémétrie reçue depuis plus que le délai de grâce."""

    CHARGING = "charging"
    """Le robot est en charge sur sa base."""

    LOW_BATTERY = "low_battery"
    """Batterie sous le seuil d'alerte."""

    OPERATIONAL = "operational"
    """Rien à signaler."""


@dataclass(frozen=True)
class Position:
    """Position planaire en mètres, dans le repère de l'entrepôt."""

    x: float
    y: float


@dataclass(frozen=True)
class Reading:
    """Une mesure de télémétrie envoyée par un robot.

    Attributes:
        robot_id: Identifiant du robot émetteur.
        timestamp_s: Horodatage de la mesure, en secondes depuis l'époque Unix.
        voltage_mv: Tension batterie mesurée, en millivolts.
        position: Position du robot au moment de la mesure.
        is_charging: Vrai si le robot est branché sur sa base de charge.
    """

    robot_id: str
    timestamp_s: float
    voltage_mv: int
    position: Position
    is_charging: bool = False
