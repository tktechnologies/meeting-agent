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
# Macro planning configuration (workstreams layer)
# ---------------------------------------------------------------------------
USE_MACRO_PLAN: bool = _env_flag("USE_MACRO_PLAN", True)
MACRO_DEFAULT_MODE: str = os.getenv("MACRO_DEFAULT_MODE", "auto")  # auto|strict|off

# ---------------------------------------------------------------------------
# Planner v3 configuration (goal-oriented, intent-driven planning)
# ---------------------------------------------------------------------------
USE_PLANNER_V3: bool = _env_flag("USE_PLANNER_V3", True)  # Enable new planner by default
PLANNER_V3_ORGS: Optional[str] = os.getenv("PLANNER_V3_ORGS")  # Comma-separated list for gradual rollout

# ---------------------------------------------------------------------------
# Automatic workstream creation
# ---------------------------------------------------------------------------
USE_AUTO_WORKSTREAMS: bool = _env_flag("USE_AUTO_WORKSTREAMS", False)  # Disabled by default (opt-in)
AUTO_WS_MIN_CLUSTER_SIZE: int = int(os.getenv("AUTO_WS_MIN_CLUSTER_SIZE", "3"))  # Min facts per workstream
AUTO_WS_MAX_PER_ORG: int = int(os.getenv("AUTO_WS_MAX_PER_ORG", "10"))  # Max auto-created workstreams
AUTO_WS_STALE_DAYS: int = int(os.getenv("AUTO_WS_STALE_DAYS", "90"))  # Days before archiving inactive workstreams

# ---------------------------------------------------------------------------
# LangGraph-based agenda planning (v2.0)
# ---------------------------------------------------------------------------
USE_LANGGRAPH_AGENDA: bool = _env_flag("USE_LANGGRAPH_AGENDA", True)  # Enabled by default - v2.0 is production-ready
LANGGRAPH_ORGS: Optional[str] = os.getenv("LANGGRAPH_ORGS")  # Comma-separated list for whitelisting (None = all orgs)
LANGGRAPH_FALLBACK_LEGACY: bool = _env_flag("LANGGRAPH_FALLBACK_LEGACY", True)  # Fallback to legacy on errors

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
