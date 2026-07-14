import logging
import os
import signal
import subprocess
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from pygments.lexers import guess_lexer_for_filename
from pygments.util import ClassNotFound
from secret_manager import get_github_token

logger = logging.getLogger(__name__)


# Directories whose contents are vendored, generated, or not source code.
# os.walk will skip these entirely — no files inside are analysed.
_SKIP_DIRS = {
    ".git", ".github", ".idea", ".vscode",
    "node_modules", "vendor", "third_party", "third-party",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".tox",
    "dist", "build", "out", "target",
    ".next", ".nuxt", ".svelte-kit",
    "coverage", ".nyc_output", "htmlcov",
    "venv", ".venv", "env", "virtualenv", "site-packages",
    "bower_components",
    ".terraform", ".terragrunt-cache",
}

# File extensions that are never programming language source code.
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp", ".tiff",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".a", ".lib", ".o", ".obj",
    ".wasm", ".pyc", ".pyo", ".pyd", ".class",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".pb", ".parquet", ".avro", ".arrow", ".npy", ".npz",
}

# Specific filenames that are auto-generated lock files or metadata.
_SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", "Gemfile.lock",
    "go.sum", "Cargo.lock", "composer.lock",
    ".DS_Store", "Thumbs.db",
    ".gitignore", ".gitattributes", ".editorconfig",
    "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md",
}

# Pygments language names that represent prose or data formats, not code.
# GitHub Linguist marks these as "prose" or "data" type and excludes them
# from the language percentage bar — we do the same.
_PROSE_AND_DATA = {
    "Markdown", "reStructuredText", "Text only", "Plain Text",
    "JSON", "YAML", "TOML", "XML", "INI",
    "CSV", "TSV",
}

# Maps specific filenames to the framework or tool they indicate.
FRAMEWORK_MAP = {
    "package.json": "Node.js",
    "requirements.txt": "Python",
    "Pipfile": "Python/Pipenv",
    "go.mod": "Go",
    "pom.xml": "Java/Maven",
    "build.gradle": "Java/Gradle",
    "Gemfile": "Ruby",
    "Cargo.toml": "Rust",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
    ".github": "GitHub Actions",
    "terraform": "Terraform",
    "helmfile.yaml": "Helm",
    "Chart.yaml": "Helm",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    ".gitlab-ci.yml": "GitLab CI",
    "Jenkinsfile": "Jenkins",
    "serverless.yml": "Serverless Framework",
}


def is_valid_github_url(repo_url: str) -> bool:
    """
    True only for a well-formed https://github.com/... URL.

    Parses the URL instead of doing a substring check so a host like
    github.com.attacker.com (which contains "github.com" but isn't it)
    is correctly rejected.
    """
    parts = urlsplit(repo_url)
    return parts.scheme == "https" and parts.hostname == "github.com"


def _build_authenticated_url(repo_url: str, token: str) -> str:
    """
    Rebuild repo_url with the token as URL userinfo, e.g.
    https://TOKEN@github.com/user/repo.git

    Only ever called after is_valid_github_url has confirmed the host is
    exactly github.com — rebuilding from the parsed, validated hostname
    (rather than string-replacing a prefix) means the token can't end up
    addressed to an attacker-chosen host.
    """
    parts = urlsplit(repo_url)
    netloc = f"{token}@{parts.hostname}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


CLONE_TIMEOUT_SECONDS = 60


def _clone_with_timeout(authenticated_url: str, dest: str, timeout: int = CLONE_TIMEOUT_SECONDS) -> None:
    """
    Run `git clone --depth=1` as a subprocess with a hard wall-clock timeout.

    GitPython's own kill_after_timeout kwarg is not reliable for this: it
    only signals the top-level `git` process it spawned, but for an https
    clone git execs a separate git-remote-https child to actually do the
    network I/O. Killing just the parent leaves that child (and the
    connection it's blocked on) running until the OS's own TCP retry
    timeout fires — around 130s on Linux — regardless of the timeout we
    asked for. Running the clone in its own process group and killing the
    whole group on timeout takes the orphaned child down too.
    """
    proc = subprocess.Popen(
        ["git", "clone", "--depth=1", "--", authenticated_url, dest],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.communicate()
        raise TimeoutError(f"git clone exceeded {timeout}s timeout")
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace"))


def clone_repo(repo_url: str) -> str:
    """
    Clone a GitHub repository into a temporary directory.
    Returns the path to the cloned repo.
    The caller is responsible for deleting the temp dir when done.
    """
    if not is_valid_github_url(repo_url):
        raise ValueError("Only https://github.com/... repository URLs are supported")

    token = get_github_token()
    # Inject the token into the URL so git can authenticate.
    # The token never appears in logs because we build the URL in memory.
    authenticated_url = _build_authenticated_url(repo_url, token)

    temp_dir = tempfile.mkdtemp(prefix="gitflow-")

    try:
        _clone_with_timeout(authenticated_url, temp_dir)
        # --depth=1 is a shallow clone — only the latest commit.
        # Full clones of large repos can be gigabytes.
        return temp_dir
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        # Exception text (git's stderr) includes the exact command it ran,
        # which contains the token embedded in authenticated_url — log a
        # redacted copy server-side and never return the raw text to the
        # caller, or the token leaks in the API response.
        logger.error("Clone failed for %s: %s", repo_url, str(e).replace(token, "***"))
        raise ValueError("Failed to clone repository — it may be private, deleted, or the URL is invalid.")


def _detect_file_language(filepath: Path) -> str | None:
    """
    Return the pygments language name for a file, or None if unrecognised
    or if the file is prose/data rather than programming language source.

    Strategy: try by filename first (fast, no file read). For ambiguous
    extensions like .h (C vs C++), pygments needs the first few bytes of
    content to score candidate lexers — we read up to 4 KB in that case.
    """
    try:
        lexer = guess_lexer_for_filename(filepath.name, "")
        name = lexer.name
        return None if name in _PROSE_AND_DATA else name
    except ClassNotFound:
        pass

    # Second attempt: read a small slice of the file so pygments can use
    # content heuristics (shebangs, keywords, class declarations, etc.)
    try:
        snippet = filepath.read_bytes()[:4096].decode("utf-8", errors="replace")
        lexer = guess_lexer_for_filename(filepath.name, snippet)
        name = lexer.name
        return None if name in _PROSE_AND_DATA else name
    except (ClassNotFound, OSError):
        return None


def detect_languages(repo_path: str) -> dict:
    """
    Walk the repo and calculate language distribution by byte size,
    the same way GitHub Linguist does.

    Returns a dict of language name to percentage of total code bytes,
    sorted descending. Example: {"Python": 62.3, "HCL": 21.1, "Shell": 16.6}
    """
    byte_counts: dict[str, int] = {}

    for root, dirs, files in os.walk(repo_path):
        # Prune in-place so os.walk does not descend into skipped dirs.
        dirs[:] = [
            d for d in dirs
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]

        for filename in files:
            if filename in _SKIP_FILENAMES:
                continue

            filepath = Path(root) / filename

            if filepath.suffix.lower() in _SKIP_EXTENSIONS:
                continue

            lang = _detect_file_language(filepath)
            if lang is None:
                continue

            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            if size == 0:
                continue

            byte_counts[lang] = byte_counts.get(lang, 0) + size

    if not byte_counts:
        return {}

    total = sum(byte_counts.values())
    return {
        lang: round((count / total) * 100, 1)
        for lang, count in sorted(byte_counts.items(), key=lambda x: x[1], reverse=True)
    }


def detect_frameworks(repo_path: str) -> list:
    """
    Check for the presence of known config files and directories
    that indicate specific frameworks and tools.
    Returns a list of detected framework names.
    """
    detected = []
    repo = Path(repo_path)

    for filename, framework in FRAMEWORK_MAP.items():
        if (repo / filename).exists():
            if framework not in detected:
                detected.append(framework)

    return detected


def analyze_repo(repo_url: str) -> dict:
    """
    Main entry point for the analyzer.
    Clones the repo, runs all detection, cleans up, returns results.
    """
    repo_path = None
    try:
        repo_path = clone_repo(repo_url)

        languages = detect_languages(repo_path)
        frameworks = detect_frameworks(repo_path)

        return {
            "repo_url": repo_url,
            "languages": languages,
            "frameworks": frameworks,
            "status": "success"
        }

    finally:
        # Always clean up the temp directory even if analysis fails.
        # Without this, every analysis leaks disk space on the server.
        if repo_path:
            shutil.rmtree(repo_path, ignore_errors=True)
