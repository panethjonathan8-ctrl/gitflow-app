import os
import logging
import requests
from urllib.parse import urlsplit
from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy.exc import OperationalError

import database

APP_VERSION = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger(__name__)


def is_valid_github_url(repo_url: str) -> bool:
    """
    True only for a well-formed https://github.com/... URL.

    Parses the URL instead of doing a substring check so a host like
    github.com.attacker.com (which contains "github.com" but isn't it)
    is correctly rejected. Mirrors the same check in analyzer and
    graph-builder — this service has no shared module to import it from.
    """
    parts = urlsplit(repo_url)
    return parts.scheme == "https" and parts.hostname == "github.com"

app = Flask(__name__)
metrics = PrometheusMetrics(app, excluded_paths=["/health"])
metrics.info("app_info", "Application info", service="result-api")

ANALYZER_URL      = os.environ.get("ANALYZER_URL", "http://analyzer:5001")
GRAPH_BUILDER_URL = os.environ.get("GRAPH_BUILDER_URL", "http://graph-builder:5002")

# Initialise DB connection at startup. If DB_HOST is not set (local dev without
# a database) we skip silently so the service still starts.
_db_engine = None
if os.environ.get("DB_HOST"):
    try:
        _db_engine = database.get_engine()
        database.init_db(_db_engine)
    except Exception as exc:
        logger.warning("Database unavailable — caching disabled: %s", exc)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "result-api"}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "GitFlow Analyzer",
        "version": "2.0.0",
        "architecture": "microservices",
        "endpoints": {
            "health": "GET /health",
            "analyze": "POST /analyze"
        }
    }), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()

    if not data or "repo_url" not in data:
        return jsonify({
            "error": "Missing repo_url",
            "example": {"repo_url": "https://github.com/user/repo"}
        }), 400

    repo_url = data["repo_url"].strip()

    if not is_valid_github_url(repo_url):
        return jsonify({"error": "Only https://github.com/... repository URLs are supported"}), 400

    logger.info("Orchestrating analysis for: %s", repo_url)

    # ── Cache check ───────────────────────────────────────────────────────────
    if _db_engine:
        try:
            cached = database.get_cached_result(_db_engine, repo_url)
            if cached:
                cached["cached"] = True
                return jsonify(cached), 200
        except OperationalError as exc:
            logger.warning("Cache read failed, proceeding without cache: %s", exc)

    try:
        # ── Analyzer ──────────────────────────────────────────────────────────
        logger.info("Calling analyzer at %s", ANALYZER_URL)
        analyzer_response = requests.post(
            f"{ANALYZER_URL}/analyze",
            json={"repo_url": repo_url},
            timeout=120
        )
        if analyzer_response.status_code == 400:
            error_msg = analyzer_response.json().get("error", "Analysis failed")
            if "clone" in error_msg.lower() or "authentication" in error_msg.lower():
                error_msg = "This repository is private or could not be accessed. GitFlow Analyzer can only analyze public GitHub repositories."
            return jsonify({"error": error_msg}), 400
        analyzer_response.raise_for_status()
        analysis = analyzer_response.json()

        # ── Graph builder ─────────────────────────────────────────────────────
        logger.info("Calling graph-builder at %s", GRAPH_BUILDER_URL)
        graph_response = requests.post(
            f"{GRAPH_BUILDER_URL}/build-graph",
            json={"repo_url": repo_url},
            timeout=120
        )
        if graph_response.status_code == 400:
            error_msg = graph_response.json().get("error", "Graph build failed")
            if "clone" in error_msg.lower() or "authentication" in error_msg.lower():
                error_msg = "This repository is private or could not be accessed. GitFlow Analyzer can only analyze public GitHub repositories."
            return jsonify({"error": error_msg}), 400
        graph_response.raise_for_status()
        graph = graph_response.json()

        result = {
            "repo_url":   repo_url,
            "languages":  analysis.get("languages", {}),
            "frameworks": analysis.get("frameworks", []),
            "graph": {
                "nodes":      graph.get("nodes", []),
                "edges":      graph.get("edges", []),
                "node_count": graph.get("node_count", 0),
                "edge_count": graph.get("edge_count", 0)
            },
            "status":  "success",
            "cached":  False,
        }

        # ── Cache store ───────────────────────────────────────────────────────
        if _db_engine:
            try:
                database.store_result(_db_engine, repo_url, result)
            except OperationalError as exc:
                logger.warning("Cache write failed: %s", exc)

        return jsonify(result), 200

    except requests.exceptions.ConnectionError as exc:
        logger.error("Service connection error: %s", exc)
        return jsonify({
            "error": "Could not connect to upstream service",
            "detail": str(exc)
        }), 503

    except requests.exceptions.Timeout:
        return jsonify({"error": "Upstream service timed out"}), 504

    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
