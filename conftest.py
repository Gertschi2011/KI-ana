import os
import sys
from pathlib import Path

# Ensure repository root on sys.path so imports like 'ki_ana.netapi' work
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Sensible defaults for tests
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("LOG_LEVEL", "WARNING")
