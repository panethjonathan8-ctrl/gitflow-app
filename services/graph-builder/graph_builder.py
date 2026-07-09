import os
import re
import tempfile
import shutil
from pathlib import Path
from git import Repo
from secret_manager import get_github_token

# Maps file extensions to display language names.
# Used to label nodes so the frontend can colour them by language.
EXTENSION_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".java": "Java",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".php": "PHP",
    ".scala": "Scala",
    ".sh": "Shell",
    ".tf": "Terraform",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
}

# Extensions we skip entirely — binaries, images, lock files, generated output.
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".exe", ".dll", ".so",
    ".pyc", ".pyo", ".class", ".wasm",
    ".mp3", ".mp4", ".wav", ".ttf", ".woff", ".woff2",
    ".lock",  # package-lock, yarn.lock, etc.
}


def parse_python_imports(file_path: str) -> list:
    """
    Extract import statements from a Python file.
    Returns a list of module names being imported.
    """
    imports = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                # Match: import os, import sys
                if line.startswith("import "):
                    module = line.replace("import ", "").split(" as ")[0].split(".")[0].strip()
                    imports.append(module)
                # Match: from flask import Flask, from .utils import helper
                elif line.startswith("from "):
                    parts = line.split(" import ")
                    if len(parts) > 0:
                        module = parts[0].replace("from ", "").split(".")[0].strip()
                        if module:
                            imports.append(module)
    except Exception:
        pass
    return imports


def parse_js_imports(file_path: str) -> list:
    """
    Extract import/require statements from a JavaScript or TypeScript file.
    """
    imports = []
    # Matches: import x from 'module' and const x = require('module')
    import_pattern = re.compile(
        r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
        re.MULTILINE
    )
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            for match in import_pattern.finditer(content):
                module = match.group(1) or match.group(2)
                if module:
                    # Strip relative imports — only keep package imports
                    if not module.startswith("."):
                        # For scoped packages like @org/pkg, keep the full name
                        imports.append(module.split("/")[0] if not module.startswith("@") else "/".join(module.split("/")[:2]))
    except Exception:
        pass
    return imports


def build_graph(repo_url: str) -> dict:
    """
    Clone the repo and build a dependency graph.

    Returns a dict with:
    - nodes: list of {id, label, type} — files and modules
    - edges: list of {source, target} — import relationships
    """
    token = get_github_token()
    temp_dir = tempfile.mkdtemp(prefix="gitflow-graph-")

    try:
        if "github.com" in repo_url:
            authenticated_url = repo_url.replace(
                "https://github.com",
                f"https://{token}@github.com"
            )
        else:
            authenticated_url = repo_url

        try:
            Repo.clone_from(authenticated_url, temp_dir, depth=1)
        except Exception as e:
            raise ValueError(f"Failed to clone repository: {str(e)}")

        nodes = []
        edges = []
        node_ids = set()

        def add_node(node_id: str, label: str, node_type: str, **extra):
            if node_id not in node_ids:
                nodes.append({"id": node_id, "label": label, "type": node_type, **extra})
                node_ids.add(node_id)

        # Walk the repo and process source files
        for root, dirs, files in os.walk(temp_dir):
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ["node_modules", "vendor", "__pycache__", "dist", "build"]
            ]

            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, temp_dir)
                file_ext = Path(file).suffix.lower()

                if file_ext in SKIP_EXTENSIONS:
                    continue

                # Only include files with a recognised extension.
                language = EXTENSION_LANGUAGE.get(file_ext)
                if language is None:
                    continue

                # Top-level directory becomes the visual group in the frontend.
                # e.g. "services/analyzer/app.py" → group "services"
                path_parts = relative_path.replace("\\", "/").split("/")
                group = path_parts[0] if len(path_parts) > 1 else "root"

                file_node_id = relative_path
                add_node(file_node_id, relative_path, "file",
                         group=group, language=language)

                # Parse imports for supported languages; others get nodes but no edges.
                if file_ext == ".py":
                    imports = parse_python_imports(file_path)
                elif file_ext in [".js", ".ts", ".jsx", ".tsx"]:
                    imports = parse_js_imports(file_path)
                else:
                    imports = []

                for module in set(imports):
                    module_node_id = f"module:{module}"
                    add_node(module_node_id, module, "module")
                    edges.append({
                        "source": file_node_id,
                        "target": module_node_id
                    })

        return {
            "repo_url": repo_url,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "status": "success"
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
