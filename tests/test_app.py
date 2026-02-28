"""Integration tests for the VRC Flask application.

All tests mock extract_claims to avoid real Claude API calls.
"""

import json
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as app_module

# Mock extraction: 3 claims, 1 attack (c1→c2), 1 support (c1→c3)
# Expected: c1 accepted, c2 rejected, c3 accepted
MOCK_EXTRACTION = {
    "claims": [
        {"id": "c1", "text": "The sky is blue"},
        {"id": "c2", "text": "The sky is green"},
        {"id": "c3", "text": "Blue light scatters more"},
    ],
    "attacks": [
        {"from": "c1", "to": "c2", "reason": "Direct contradiction"},
    ],
    "supports": [
        {"from": "c1", "to": "c3", "reason": "Scientific basis"},
    ],
}


# ── Health & Index ───────────────────────────────────────────────────────

class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "vrc"

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ── Feed ─────────────────────────────────────────────────────────────────

class TestFeed:
    def test_feed_empty(self, client):
        resp = client.get("/feed")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["items"] == []

    def test_feed_after_analyze(self, client):
        with patch.object(app_module, "extract_claims", return_value=MOCK_EXTRACTION):
            client.post("/analyze", json={"text": "Some argument text here."})
        resp = client.get("/feed")
        data = resp.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["handle"] == "anon"


# ── History ──────────────────────────────────────────────────────────────

class TestHistory:
    def test_history_empty(self, client):
        resp = client.get("/history")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ── Analyze ──────────────────────────────────────────────────────────────

class TestAnalyze:
    def test_analyze_success(self, client):
        with patch.object(app_module, "extract_claims", return_value=MOCK_EXTRACTION):
            resp = client.post("/analyze", json={"text": "Some argument text here."})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "claims" in data
        assert "attacks" in data
        assert "supports" in data
        assert "analysis" in data
        assert "vrc" in data
        assert "id" in data
        assert data["handle"] == "anon"

    def test_analyze_empty_text(self, client):
        resp = client.post("/analyze", json={"text": ""})
        assert resp.status_code == 400

    def test_analyze_too_long(self, client):
        resp = client.post("/analyze", json={"text": "x" * 15001})
        assert resp.status_code == 400

    def test_analyze_custom_handle(self, client):
        with patch.object(app_module, "extract_claims", return_value=MOCK_EXTRACTION):
            resp = client.post("/analyze", json={"text": "Argument.", "handle": "alice"})
        data = resp.get_json()
        assert data["handle"] == "alice"


# ── Handle Sanitization ─────────────────────────────────────────────────

class TestHandleSanitization:
    def test_none_handle(self):
        assert app_module._sanitize_handle(None) == "anon"

    def test_empty_handle(self):
        assert app_module._sanitize_handle("") == "anon"

    def test_at_prefix_stripped(self):
        assert app_module._sanitize_handle("@alice") == "alice"

    def test_valid_passthrough(self):
        assert app_module._sanitize_handle("bob_99") == "bob_99"

    def test_too_short(self):
        assert app_module._sanitize_handle("a") == "anon"

    def test_too_long(self):
        assert app_module._sanitize_handle("a" * 25) == "anon"

    def test_invalid_chars(self):
        assert app_module._sanitize_handle("no spaces!") == "anon"


# ── Analysis CRUD ────────────────────────────────────────────────────────

class TestAnalysisCRUD:
    def test_create_and_get(self, client):
        with patch.object(app_module, "extract_claims", return_value=MOCK_EXTRACTION):
            create_resp = client.post("/analyze", json={"text": "Test text.", "handle": "tester"})
        analysis_id = create_resp.get_json()["id"]

        get_resp = client.get(f"/analysis/{analysis_id}")
        assert get_resp.status_code == 200
        data = get_resp.get_json()
        assert data["source_text"] == "Test text."
        assert data["handle"] == "tester"

    def test_get_not_found(self, client):
        resp = client.get("/analysis/999999")
        assert resp.status_code == 404

    def test_delete_then_404(self, client):
        with patch.object(app_module, "extract_claims", return_value=MOCK_EXTRACTION):
            create_resp = client.post("/analyze", json={"text": "Delete me."})
        analysis_id = create_resp.get_json()["id"]

        del_resp = client.delete(f"/analysis/{analysis_id}")
        assert del_resp.status_code == 200

        get_resp = client.get(f"/analysis/{analysis_id}")
        assert get_resp.status_code == 404
