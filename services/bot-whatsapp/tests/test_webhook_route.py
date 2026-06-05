#genai: Sprint 5 — webhook endpoint integration test via TestClient.
"""
Spins up the FastAPI app with the mock BSP injected, posts a webhook payload,
and asserts that:
  - the response is 200,
  - the conversation produced an outbound message into MockBsp.outbox,
  - replaying the same webhook produces no second outbound (dedup).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_and_bsp():
    from app.bsp.mock import MockBsp
    from app.main import app
    from app.webhook import set_bsp_for_tests

    mock = MockBsp()
    set_bsp_for_tests(mock)
    return TestClient(app), mock


def test_webhook_text_message_triggers_welcome(client_and_bsp):
    client, mock = client_and_bsp
    payload = {"from": "+919900111222", "kind": "text", "text": "hi",
               "message_id": "wh-1"}
    resp = client.post("/whatsapp/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert mock.outbox
    assert "business name" in (mock.outbox[0].text or "").lower()


def test_webhook_dedups_duplicate_message_id(client_and_bsp):
    client, mock = client_and_bsp
    payload = {"from": "+919900111333", "kind": "text", "text": "hi",
               "message_id": "wh-dup"}
    client.post("/whatsapp/webhook", json=payload)
    before = len(mock.outbox)
    # Replay same message_id.
    client.post("/whatsapp/webhook", json=payload)
    assert len(mock.outbox) == before


def test_health_endpoint(client_and_bsp):
    client, _ = client_and_bsp
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "bot-whatsapp"
