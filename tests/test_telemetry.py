"""Corrigé du TD 1 — jeu de tests de référence sur fleet_api.telemetry.

Sur le dépôt tel qu'il est distribué, ce fichier fait tomber exactement trois
tests, correspondant aux trois bugs volontaires :

  * test_is_low_battery_au_seuil_exact          -> BUG 1 (borne)
  * test_path_length_m_deux_points              -> BUG 2 (off-by-one)
  * test_path_length_m_trois_points             -> BUG 2 (off-by-one)
  * test_fleet_summary_flotte_vide              -> BUG 3 (collection vide)

Une fois les trois bugs corrigés, tout passe au vert.
"""

import pytest

from fleet_api.models import Position, Reading, RobotState
from fleet_api.telemetry import (
    average_speed_mps,
    detect_voltage_dropouts,
    estimate_runtime_minutes,
    fleet_summary,
    is_low_battery,
    median_voltage_mv,
    path_length_m,
    robot_state,
)


def reading(
    voltage_mv: int = 12_600,
    timestamp_s: float = 1_000.0,
    robot_id: str = "r1",
    is_charging: bool = False,
) -> Reading:
    """Fabrique une mesure, pour éviter de répéter les mêmes arguments."""
    return Reading(
        robot_id=robot_id,
        timestamp_s=timestamp_s,
        voltage_mv=voltage_mv,
        position=Position(0, 0),
        is_charging=is_charging,
    )


# --------------------------------------------------------------------------
# is_low_battery
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("niveau", "attendu"),
    [
        (0.0, True),
        (10.0, True),
        (19.9, True),
        (20.1, False),
        (50.0, False),
        (100.0, False),
    ],
)
def test_is_low_battery_de_part_et_dautre_du_seuil(niveau, attendu):
    assert is_low_battery(niveau) is attendu


def test_is_low_battery_au_seuil_exact():
    """La spec dit « inférieur OU ÉGAL » : 20 % est en alerte."""
    assert is_low_battery(20.0) is True


def test_is_low_battery_seuil_personnalise():
    assert is_low_battery(35.0, threshold_pct=35.0) is True
    assert is_low_battery(35.1, threshold_pct=35.0) is False


# --------------------------------------------------------------------------
# path_length_m
# --------------------------------------------------------------------------


def test_path_length_m_trajet_vide():
    assert path_length_m([]) == 0.0


def test_path_length_m_un_seul_point():
    assert path_length_m([Position(1, 1)]) == 0.0


def test_path_length_m_deux_points():
    """Deux points : la longueur est la distance entre eux."""
    assert path_length_m([Position(0, 0), Position(3, 4)]) == pytest.approx(5.0)


def test_path_length_m_trois_points():
    """Trois points en L : 3 m puis 4 m, soit 7 m au total."""
    trajet = [Position(0, 0), Position(3, 0), Position(3, 4)]
    assert path_length_m(trajet) == pytest.approx(7.0)


def test_path_length_m_aller_retour():
    """Un aller-retour compte la distance deux fois."""
    trajet = [Position(0, 0), Position(5, 0), Position(0, 0)]
    assert path_length_m(trajet) == pytest.approx(10.0)


# --------------------------------------------------------------------------
# average_speed_mps
# --------------------------------------------------------------------------


def test_average_speed_mps_cas_nominal():
    assert average_speed_mps(10.0, 5.0) == pytest.approx(2.0)


@pytest.mark.parametrize("duree", [0.0, -1.0])
def test_average_speed_mps_duree_non_positive(duree):
    assert average_speed_mps(10.0, duree) is None


def test_average_speed_mps_trajet_immobile():
    assert average_speed_mps(0.0, 5.0) == 0.0


# --------------------------------------------------------------------------
# estimate_runtime_minutes
# --------------------------------------------------------------------------


def test_estimate_runtime_minutes_cas_nominal():
    assert estimate_runtime_minutes(50.0, 2.0) == pytest.approx(25.0)


def test_estimate_runtime_minutes_arrondi():
    assert estimate_runtime_minutes(100.0, 3.0) == 33.3


@pytest.mark.parametrize("conso", [0.0, -1.0])
def test_estimate_runtime_minutes_sans_consommation(conso):
    assert estimate_runtime_minutes(50.0, conso) is None


def test_estimate_runtime_minutes_batterie_vide():
    assert estimate_runtime_minutes(0.0, 2.0) == 0.0


# --------------------------------------------------------------------------
# median_voltage_mv
# --------------------------------------------------------------------------


def test_median_voltage_mv_liste_vide():
    assert median_voltage_mv([]) is None


def test_median_voltage_mv_nombre_impair():
    mesures = [reading(voltage_mv=v) for v in (11_000, 12_000, 10_000)]
    assert median_voltage_mv(mesures) == 11_000


def test_median_voltage_mv_nombre_pair():
    """Sur un nombre pair, la médiane est la moyenne des deux valeurs centrales."""
    mesures = [reading(voltage_mv=v) for v in (10_000, 11_000, 12_000, 13_000)]
    assert median_voltage_mv(mesures) == pytest.approx(11_500)


# --------------------------------------------------------------------------
# robot_state
# --------------------------------------------------------------------------


def test_robot_state_operationnel():
    assert (
        robot_state(reading(voltage_mv=12_600, timestamp_s=1_000), now_s=1_010)
        is RobotState.OPERATIONAL
    )


def test_robot_state_batterie_basse():
    # 10 700 mV -> environ 9,5 %
    assert (
        robot_state(reading(voltage_mv=10_700, timestamp_s=1_000), now_s=1_010)
        is RobotState.LOW_BATTERY
    )


def test_robot_state_en_charge():
    assert (
        robot_state(reading(timestamp_s=1_000, is_charging=True), now_s=1_010)
        is RobotState.CHARGING
    )


def test_robot_state_hors_ligne():
    assert robot_state(reading(timestamp_s=1_000), now_s=1_200) is RobotState.OFFLINE


def test_robot_state_hors_ligne_prime_sur_batterie_basse():
    """L'ordre des règles compte : hors ligne l'emporte sur batterie basse."""
    vieille = reading(voltage_mv=10_600, timestamp_s=1_000)
    assert robot_state(vieille, now_s=1_200) is RobotState.OFFLINE


def test_robot_state_hors_ligne_prime_sur_en_charge():
    vieille = reading(timestamp_s=1_000, is_charging=True)
    assert robot_state(vieille, now_s=1_200) is RobotState.OFFLINE


def test_robot_state_en_charge_prime_sur_batterie_basse():
    en_charge = reading(voltage_mv=10_600, timestamp_s=1_000, is_charging=True)
    assert robot_state(en_charge, now_s=1_010) is RobotState.CHARGING


def test_robot_state_juste_au_delai_de_grace():
    """La spec dit « plus de grace_s » : exactement grace_s n'est pas hors ligne."""
    assert (
        robot_state(reading(timestamp_s=1_000), now_s=1_120) is not RobotState.OFFLINE
    )


# --------------------------------------------------------------------------
# detect_voltage_dropouts
# --------------------------------------------------------------------------


def test_detect_voltage_dropouts_liste_vide():
    assert detect_voltage_dropouts([], max_drop_mv=100) == []


def test_detect_voltage_dropouts_une_seule_mesure():
    assert detect_voltage_dropouts([reading()], max_drop_mv=100) == []


def test_detect_voltage_dropouts_aucune_chute():
    mesures = [reading(voltage_mv=v) for v in (12_000, 11_950, 11_900)]
    assert detect_voltage_dropouts(mesures, max_drop_mv=100) == []


def test_detect_voltage_dropouts_une_chute():
    mesures = [reading(voltage_mv=v) for v in (12_000, 11_500, 11_450)]
    assert detect_voltage_dropouts(mesures, max_drop_mv=100) == [1]


def test_detect_voltage_dropouts_plusieurs_chutes():
    mesures = [reading(voltage_mv=v) for v in (12_000, 11_500, 11_450, 10_900)]
    assert detect_voltage_dropouts(mesures, max_drop_mv=100) == [1, 3]


def test_detect_voltage_dropouts_chute_exactement_au_seuil():
    """« strictement plus » : une chute égale au seuil n'est pas signalée."""
    mesures = [reading(voltage_mv=v) for v in (12_000, 11_900)]
    assert detect_voltage_dropouts(mesures, max_drop_mv=100) == []


def test_detect_voltage_dropouts_remontee_ignoree():
    """Une remontée de tension n'est jamais une chute."""
    mesures = [reading(voltage_mv=v) for v in (11_000, 12_000)]
    assert detect_voltage_dropouts(mesures, max_drop_mv=100) == []


# --------------------------------------------------------------------------
# fleet_summary
# --------------------------------------------------------------------------


def test_fleet_summary_flotte_vide():
    """Une flotte vide est un cas valide, pas une erreur."""
    assert fleet_summary([]) == {
        "robot_count": 0,
        "average_battery_pct": 0.0,
        "low_battery_count": 0,
    }


def test_fleet_summary_un_robot():
    resume = fleet_summary([reading(voltage_mv=12_600)])
    assert resume == {
        "robot_count": 1,
        "average_battery_pct": 100.0,
        "low_battery_count": 0,
    }


def test_fleet_summary_moyenne_et_comptage():
    mesures = [
        reading(voltage_mv=12_600, robot_id="r1"),  # 100 %
        reading(voltage_mv=11_550, robot_id="r2"),  # 50 %
        reading(voltage_mv=10_500, robot_id="r3"),  # 0 %  -> en alerte
    ]
    resume = fleet_summary(mesures)
    assert resume["robot_count"] == 3
    assert resume["average_battery_pct"] == pytest.approx(50.0)
    assert resume["low_battery_count"] == 1


def test_fleet_summary_seuil_personnalise():
    mesures = [
        reading(voltage_mv=12_600, robot_id="r1"),  # 100 %
        reading(voltage_mv=11_550, robot_id="r2"),  # 50 %
    ]
    assert fleet_summary(mesures, threshold_pct=60.0)["low_battery_count"] == 1
