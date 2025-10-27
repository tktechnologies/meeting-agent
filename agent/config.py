import os
from pathlib import Path
from typing import Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / '.env'
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # dotenv not installed, rely on system environment

# ==============================================================================
# AI MODEL CONFIGURATION
# ==============================================================================

# Model Provider Selection
# ⭐ PADRÃO: Google Gemini 2.5 Pro (GPT-5 descontinuado - retorna 0 chars)
MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "google")  # openai, google, or anthropic

# OpenAI Configuration
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-5")  # ✅ GPT-5 configurado

# Google Gemini Configuration
GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")

# Anthropic Claude Configuration
ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL_NAME: str = os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-5")

# Model Settings
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4000"))

# Search API
TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")

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
# MongoDB storage configuration
# ---------------------------------------------------------------------------
USE_MONGODB_STORAGE: bool = _env_flag("USE_MONGODB_STORAGE", False)
CHAT_AGENT_URL: str = os.getenv("CHAT_AGENT_URL", "http://localhost:5000")
SERVICE_TOKEN: Optional[str] = os.getenv("SERVICE_TOKEN")

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
# Deep Research Agent Integration (Feature Flag)
# ---------------------------------------------------------------------------
DEEPRESEARCH_ENABLED: bool = _env_flag("DEEPRESEARCH_ENABLED", True)  # ✅ Enabled by default - production ready
DEEPRESEARCH_API_URL: str = os.getenv("DEEPRESEARCH_API_URL", "https://deepresearch-agent.niceforest-9298afc9.eastus2.azurecontainerapps.io")
DEEPRESEARCH_MODEL: str = os.getenv("DEEPRESEARCH_MODEL", "gemini")  # ⭐ "gemini" as default (validated E2E)
DEEPRESEARCH_SEARCH_PROVIDER: str = os.getenv("DEEPRESEARCH_SEARCH_PROVIDER", "tavily")  # Always tavily
DEEPRESEARCH_TIMEOUT: int = int(os.getenv("DEEPRESEARCH_TIMEOUT", "300"))  # 5 minutes default
DEEPRESEARCH_MAX_STEPS: int = int(os.getenv("DEEPRESEARCH_MAX_STEPS", "10"))  # Deep research for meetings
DEEPRESEARCH_PERSIST_RESULTS: bool = _env_flag("DEEPRESEARCH_PERSIST_RESULTS", True)  # Save to MongoDB
DEEPRESEARCH_API_KEY: Optional[str] = os.getenv("DEEPRESEARCH_API_KEY")  # Optional authentication
DEEPRESEARCH_ORGS: Optional[str] = os.getenv("DEEPRESEARCH_ORGS")  # Comma-separated list for whitelisting
DEEPRESEARCH_MIN_CONFIDENCE: float = float(os.getenv("DEEPRESEARCH_MIN_CONFIDENCE", "0.6"))  # Min confidence to trigger
DEEPRESEARCH_FALLBACK_BASIC: bool = _env_flag("DEEPRESEARCH_FALLBACK_BASIC", True)  # Fallback to basic search on error

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


# ---------------------------------------------------------------------------
# Deep Research Integration Helpers
# ---------------------------------------------------------------------------

def is_deepresearch_enabled() -> bool:
    """
    Check if Deep Research integration is globally enabled.
    
    Returns:
        True if DEEPRESEARCH_ENABLED=true
    """
    return DEEPRESEARCH_ENABLED


def is_deepresearch_enabled_for_org(org_id: str) -> bool:
    """
    Check if Deep Research is enabled for a specific organization.
    
    Args:
        org_id: Organization identifier
    
    Returns:
        True if Deep Research is enabled globally AND (no whitelist OR org in whitelist)
    
    Examples:
        # Global enabled, no whitelist → all orgs
        DEEPRESEARCH_ENABLED=true
        DEEPRESEARCH_ORGS=
        → is_deepresearch_enabled_for_org("any_org") = True
        
        # Global enabled, with whitelist → only whitelisted
        DEEPRESEARCH_ENABLED=true
        DEEPRESEARCH_ORGS=org_acme,org_techcorp
        → is_deepresearch_enabled_for_org("org_acme") = True
        → is_deepresearch_enabled_for_org("org_other") = False
        
        # Global disabled → no orgs
        DEEPRESEARCH_ENABLED=false
        → is_deepresearch_enabled_for_org("any_org") = False
    """
    # First check global flag
    if not DEEPRESEARCH_ENABLED:
        return False
    
    # If no whitelist, enabled for all orgs
    if not DEEPRESEARCH_ORGS:
        return True
    
    # Check if org in whitelist
    whitelist = [o.strip() for o in DEEPRESEARCH_ORGS.split(",") if o.strip()]
    return org_id in whitelist


def get_deepresearch_config() -> dict:
    """
    Get Deep Research configuration as dictionary.
    
    Returns:
        Configuration dict with all Deep Research settings
    """
    return {
        "enabled": DEEPRESEARCH_ENABLED,
        "api_url": DEEPRESEARCH_API_URL,
        "model": DEEPRESEARCH_MODEL,
        "timeout": DEEPRESEARCH_TIMEOUT,
        "max_steps": DEEPRESEARCH_MAX_STEPS,
        "api_key": DEEPRESEARCH_API_KEY,
        "orgs_whitelist": DEEPRESEARCH_ORGS,
        "min_confidence": DEEPRESEARCH_MIN_CONFIDENCE,
        "fallback_basic": DEEPRESEARCH_FALLBACK_BASIC
    }
