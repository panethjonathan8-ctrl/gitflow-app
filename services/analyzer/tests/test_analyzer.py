import os
import tempfile
from pathlib import Path

from analyzer import detect_frameworks, detect_languages


# ── detect_languages ──────────────────────────────────────────────────────────

def test_detect_languages_returns_python_for_py_file():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("def hello(): return 'world'")
        result = detect_languages(tmp)
    assert "Python" in result


def test_detect_languages_empty_dir_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        result = detect_languages(tmp)
    assert result == {}


def test_detect_languages_percentages_sum_to_100():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("x = 1\n" * 50)
        Path(tmp, "script.sh").write_text("#!/bin/bash\necho hi\n" * 10)
        result = detect_languages(tmp)
    total = sum(result.values())
    assert abs(total - 100.0) < 0.2  # rounding may cause tiny drift


def test_detect_languages_skips_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(f"{tmp}/node_modules")
        Path(tmp, "node_modules", "index.js").write_text("const x = 1;")
        result = detect_languages(tmp)
    assert result == {}


def test_detect_languages_skips_image_files():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "photo.png").write_bytes(b"\x89PNG")
        result = detect_languages(tmp)
    assert result == {}


def test_detect_languages_skips_empty_files():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "empty.py").write_text("")
        result = detect_languages(tmp)
    assert result == {}


# ── detect_frameworks ─────────────────────────────────────────────────────────

def test_detect_frameworks_requirements_txt():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "requirements.txt").write_text("flask==3.0.0")
        result = detect_frameworks(tmp)
    assert "Python" in result


def test_detect_frameworks_dockerfile():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "Dockerfile").write_text("FROM python:3.12-slim")
        result = detect_frameworks(tmp)
    assert "Docker" in result


def test_detect_frameworks_chart_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "Chart.yaml").write_text("apiVersion: v2\nname: myapp")
        result = detect_frameworks(tmp)
    assert "Helm" in result


def test_detect_frameworks_go_mod():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "go.mod").write_text("module example.com/app\n\ngo 1.21")
        result = detect_frameworks(tmp)
    assert "Go" in result


def test_detect_frameworks_empty_dir_returns_empty_list():
    with tempfile.TemporaryDirectory() as tmp:
        result = detect_frameworks(tmp)
    assert result == []


def test_detect_frameworks_no_duplicates():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "Dockerfile").write_text("FROM python:3.12-slim")
        Path(tmp, "docker-compose.yml").write_text("version: '3'")
        result = detect_frameworks(tmp)
    assert result.count("Docker") == 1
