import os
import logging
from flask import Flask, request, jsonify
from analyzer import analyze_repo
from prometheus_flask_exporter import PrometheusMetrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
metrics = PrometheusMetrics(app, excluded_paths=["/health"])
metrics.info("app_info", "Application info", service="analyzer")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "analyzer"}), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Accepts a repo URL and returns detected languages and frameworks.
    Called by result-api, not directly by users.
    """
    data = request.get_json()

    if not data or "repo_url" not in data:
        return jsonify({"error": "Missing repo_url"}), 400

    repo_url = data["repo_url"].strip()

    if "github.com" not in repo_url:
        return jsonify({"error": "Only GitHub repos supported"}), 400

    logger.info(f"Analyzing: {repo_url}")

    try:
        result = analyze_repo(repo_url)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e), "status": "failed"}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
