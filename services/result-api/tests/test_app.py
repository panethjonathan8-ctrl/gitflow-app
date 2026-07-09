import json
from unittest.mock import MagicMock, patch

import pytest

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_correct_body(client):
    response = client.get("/health")
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "result-api"


# ── / ─────────────────────────────────────────────────────────────────────────

def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_index_lists_endpoints(client):
    response = client.get("/")
    data = response.get_json()
    assert "endpoints" in data


# ── /analyze input validation ─────────────────────────────────────────────────

def test_analyze_no_body_returns_400(client):
    response = client.post("/analyze", content_type="application/json")
    assert response.status_code == 400


def test_analyze_empty_json_returns_400(client):
    response = client.post(
        "/analyze",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_analyze_non_github_url_returns_400(client):
    response = client.post(
        "/analyze",
        data=json.dumps({"repo_url": "https://gitlab.com/user/repo"}),
        content_type="application/json",
    )
    assert response.status_code == 400


# ── /analyze upstream orchestration ──────────────────────────────────────────

def test_analyze_calls_both_upstream_services(client):
    mock_analysis = {"languages": {"Python": 100.0}, "frameworks": ["Flask"]}
    mock_graph = {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}

    with patch("app.requests.post") as mock_post:
        analyzer_resp = MagicMock()
        analyzer_resp.json.return_value = mock_analysis
        analyzer_resp.raise_for_status = MagicMock()

        graph_resp = MagicMock()
        graph_resp.json.return_value = mock_graph
        graph_resp.raise_for_status = MagicMock()

        mock_post.side_effect = [analyzer_resp, graph_resp]

        response = client.post(
            "/analyze",
            data=json.dumps({"repo_url": "https://github.com/user/repo"}),
            content_type="application/json",
        )

    assert response.status_code == 200
    assert mock_post.call_count == 2


def test_analyze_merges_upstream_responses(client):
    mock_analysis = {"languages": {"Python": 80.0, "Bash": 20.0}, "frameworks": ["Docker"]}
    mock_graph = {"nodes": [{"id": "main.py"}], "edges": [], "node_count": 1, "edge_count": 0}

    with patch("app.requests.post") as mock_post:
        analyzer_resp = MagicMock()
        analyzer_resp.json.return_value = mock_analysis
        analyzer_resp.raise_for_status = MagicMock()

        graph_resp = MagicMock()
        graph_resp.json.return_value = mock_graph
        graph_resp.raise_for_status = MagicMock()

        mock_post.side_effect = [analyzer_resp, graph_resp]

        response = client.post(
            "/analyze",
            data=json.dumps({"repo_url": "https://github.com/user/repo"}),
            content_type="application/json",
        )

    data = response.get_json()
    assert data["status"] == "success"
    assert data["languages"] == {"Python": 80.0, "Bash": 20.0}
    assert data["frameworks"] == ["Docker"]
    assert data["graph"]["node_count"] == 1
