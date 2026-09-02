"""Tests de l'API HTTP.

Ces tests n'ont besoin d'aucune base de données : le stockage en mémoire est
substitué au stockage réel par une surcharge de dépendance FastAPI. C'est ce
qui les rend rapides et exécutables partout.

Les tests d'intégration contre PostgreSQL arrivent en séance 5, dans
`test_integration.py`, marqués `@pytest.mark.integration`.
"""

import pytest
from fastapi.testclient import TestClient

from fleet_api.api import app, get_store
from fleet_api.store import MemoryStore


@pytest.fixture
def client():
    """Un client HTTP branché sur un stockage en mémoire vierge."""
    store = MemoryStore()
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def envoyer(client, robot_id="r1", ts=1000.0, mv=12_600, x=0.0, y=0.0, charge=False):
    """Raccourci d'envoi d'une mesure."""
    return client.post(
        f"/robots/{robot_id}/telemetry",
        json={
            "timestamp_s": ts,
            "voltage_mv": mv,
            "x": x,
            "y": y,
            "is_charging": charge,
        },
    )


def test_health_repond_ok(client):
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok", "storage": "ok"}


def test_version_expose_la_version_du_paquet(client):
    from fleet_api import __version__

    assert client.get("/version").json() == {"version": __version__}


def test_ingestion_puis_lecture(client):
    assert envoyer(client, mv=11_550).status_code == 201

    corps = client.get("/robots/r1").json()
    assert corps["robot_id"] == "r1"
    assert corps["battery_pct"] == 50.0


def test_robot_inconnu_renvoie_404(client):
    reponse = client.get("/robots/fantome")
    assert reponse.status_code == 404
    assert "fantome" in reponse.json()["detail"]


def test_tension_hors_bornes_rejetee(client):
    """La validation pydantic refuse une tension aberrante."""
    assert envoyer(client, mv=999_999).status_code == 422


def test_distance_parcourue_cumulee(client):
    """Trois positions en L : 3 m puis 4 m."""
    envoyer(client, ts=1000.0, x=0, y=0)
    envoyer(client, ts=1001.0, x=3, y=0)
    envoyer(client, ts=1002.0, x=3, y=4)

    assert client.get("/robots/r1").json()["distance_travelled_m"] == pytest.approx(7.0)


def test_fleet_agrege_le_dernier_etat_de_chaque_robot(client):
    envoyer(client, robot_id="r1", ts=1000.0, mv=12_600)
    envoyer(client, robot_id="r1", ts=1001.0, mv=11_550)  # r1 se décharge
    envoyer(client, robot_id="r2", ts=1000.0, mv=10_500)

    resume = client.get("/fleet").json()
    assert resume["robot_count"] == 2
    assert resume["average_battery_pct"] == pytest.approx(25.0)
    assert resume["low_battery_count"] == 1


def test_fleet_vide(client):
    assert client.get("/fleet").json() == {
        "robot_count": 0,
        "average_battery_pct": 0.0,
        "low_battery_count": 0,
    }
