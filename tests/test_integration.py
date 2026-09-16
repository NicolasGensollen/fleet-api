"""Tests d'intégration contre une vraie base PostgreSQL.

Ces tests sont marqués `integration` : ils sont ignorés si `DATABASE_URL`
n'est pas défini, ce qui permet à la suite unitaire de tourner partout.

    # en local, avec la base du compose
    docker compose up -d db
    DATABASE_URL=postgresql://app:app@localhost:5432/fleet uv run pytest -m integration

    # sans base
    uv run pytest -m "not integration"

Ce qu'ils vérifient et que les tests unitaires ne peuvent pas voir : que le SQL
est valide, que le schéma correspond au code, que les types survivent à
l'aller-retour, et que l'agrégation « dernière mesure par robot » est correcte
une fois exprimée en SQL.
"""

import os

import pytest

from fleet_api.models import Position, Reading
from fleet_api.store import PostgresStore

pytestmark = pytest.mark.integration

DSN = os.environ.get("DATABASE_URL")

if not DSN:
    pytest.skip("DATABASE_URL non défini", allow_module_level=True)


@pytest.fixture
def store():
    """Un dépôt vierge pour chaque test.

    On vide la table plutôt que de recréer la base : c'est bien plus rapide, et
    l'isolation entre tests est ce qui compte, pas la virginité du schéma.
    """
    s = PostgresStore(DSN)
    with s._connect() as conn:
        conn.execute("TRUNCATE readings")
    return s


def mesure(robot_id="r1", ts=1000.0, mv=12_600, x=0.0, y=0.0, charge=False) -> Reading:
    return Reading(
        robot_id=robot_id,
        timestamp_s=ts,
        voltage_mv=mv,
        position=Position(x=x, y=y),
        is_charging=charge,
    )


def test_ping(store):
    assert store.ping() is True


def test_aller_retour_conserve_les_valeurs(store):
    """Le type et la valeur survivent au passage par la base."""
    store.add(mesure(mv=11_550, x=1.5, y=-2.25, charge=True))

    lue = store.latest("r1")
    assert lue is not None
    assert lue.robot_id == "r1"
    assert lue.voltage_mv == 11_550
    assert lue.position == Position(x=1.5, y=-2.25)
    assert lue.is_charging is True


def test_latest_renvoie_la_plus_recente_pas_la_derniere_inseree(store):
    """Insertion dans le désordre : c'est l'horodatage qui tranche, pas l'ordre."""
    store.add(mesure(ts=2000.0, mv=11_000))
    store.add(mesure(ts=1000.0, mv=12_000))

    assert store.latest("r1").voltage_mv == 11_000


def test_latest_robot_inconnu(store):
    assert store.latest("fantome") is None


def test_latest_all_une_ligne_par_robot(store):
    store.add(mesure(robot_id="r1", ts=1000.0, mv=12_000))
    store.add(mesure(robot_id="r1", ts=2000.0, mv=11_000))
    store.add(mesure(robot_id="r2", ts=1500.0, mv=10_800))

    dernieres = {r.robot_id: r.voltage_mv for r in store.latest_all()}
    assert dernieres == {"r1": 11_000, "r2": 10_800}


def test_latest_all_flotte_vide(store):
    assert store.latest_all() == []


def test_history_ordre_et_limite(store):
    for i in range(5):
        store.add(mesure(ts=1000.0 + i, mv=12_000 - i * 100))

    historique = store.history("r1", limit=3)
    assert [r.timestamp_s for r in historique] == [1004.0, 1003.0, 1002.0]


def test_history_isole_les_robots(store):
    store.add(mesure(robot_id="r1"))
    store.add(mesure(robot_id="r2"))

    assert len(store.history("r1")) == 1
