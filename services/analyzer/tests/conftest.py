import sys
from pathlib import Path

# Add the service directory to the path so tests can import service modules
# without installing the package. This makes `from analyzer import ...` work
# when pytest is run from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))
