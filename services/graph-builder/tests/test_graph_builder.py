import tempfile

from graph_builder import parse_js_imports, parse_python_imports


# ── parse_python_imports ──────────────────────────────────────────────────────

def test_parse_python_imports_simple():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("import os\nimport sys\n")
        path = f.name
    result = parse_python_imports(path)
    assert "os" in result
    assert "sys" in result


def test_parse_python_imports_from_style():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("from flask import Flask\nfrom pathlib import Path\n")
        path = f.name
    result = parse_python_imports(path)
    assert "flask" in result
    assert "pathlib" in result


def test_parse_python_imports_alias():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("import numpy as np\n")
        path = f.name
    result = parse_python_imports(path)
    assert "numpy" in result


def test_parse_python_imports_submodule():
    # Only the top-level package should be captured, not the submodule
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("import os.path\n")
        path = f.name
    result = parse_python_imports(path)
    assert "os" in result
    assert "os.path" not in result


def test_parse_python_imports_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("")
        path = f.name
    result = parse_python_imports(path)
    assert result == []


def test_parse_python_imports_comments_ignored():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("# import os\nx = 1\n")
        path = f.name
    result = parse_python_imports(path)
    assert result == []


# ── parse_js_imports ──────────────────────────────────────────────────────────

def test_parse_js_imports_es6():
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write("import React from 'react';\nimport axios from 'axios';\n")
        path = f.name
    result = parse_js_imports(path)
    assert "react" in result
    assert "axios" in result


def test_parse_js_imports_require():
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write("const express = require('express');\n")
        path = f.name
    result = parse_js_imports(path)
    assert "express" in result


def test_parse_js_imports_skips_relative():
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write("import helper from './utils';\nimport config from '../config';\n")
        path = f.name
    result = parse_js_imports(path)
    assert result == []


def test_parse_js_imports_scoped_package():
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write("import { Button } from '@mui/material';\n")
        path = f.name
    result = parse_js_imports(path)
    assert "@mui/material" in result


def test_parse_js_imports_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write("")
        path = f.name
    result = parse_js_imports(path)
    assert result == []
