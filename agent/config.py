import os
from pathlib import Path
from typing import Optional

_DEF_DB_FILENAME = "spine_dev.sqlite3"

def _resolve_default_db_path() -> str:
    base_dir = Path(__file__).resolve().parents[1]
    return str(base_dir / _DEF_DB_FILENAME)

_db_env = os.getenv("SPINE_DB_PATH")
if _db_env and _db_env.strip():
    DB_PATH = os.path.abspath(_db_env)
else:
    DB_PATH = _resolve_default_db_path()

def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}

FTS_ENABLED: bool = _env_flag("SPINE_FTS_ENABLED", True)
DEFAULT_ORG_ID: str = os.getenv("DEFAULT_ORG_ID", "org_demo")

# ---------------------------------------------------------------------------
# Backwards compatibility helpers (legacy callers still import these)
# ---------------------------------------------------------------------------

def spine_db_path() -> str:
    return DB_PATH

def default_timezone() -> str:
    return os.environ.get("MEETING_AGENT_TZ", "America/Sao_Paulo")

def default_window_days() -> int:
    try:
        return int(os.environ.get("MEETING_AGENT_WINDOW_DAYS", "60"))
    except Exception:
        return 60

def default_duration_minutes() -> int:
    try:
        return int(os.environ.get("MEETING_AGENT_DURATION_MIN", "30"))
    except Exception:
        return 30

def default_org_name() -> Optional[str]:
    return os.environ.get("MEETING_AGENT_DEFAULT_ORG")
