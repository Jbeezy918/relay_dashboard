"""
Agent FS Guard (PRO)
- Local, file-backed capability tokens with audit log + countdown helper.
- Atomic saves; optional file lock if `filelock` is installed.

Public API (compatible with regular):
- list_agents() -> list[str]
- register_agent(agent_name: str, notes: str = "")
- issue_token(agent: str, scopes: list[str] | None = None, ttl_minutes: int = 30) -> (token: str, info: dict)
- list_active_tokens(agent: str | None = None) -> dict[token, info]
- revoke_token(token: str) -> bool
- check_token(token: str, needed_scope: str, expected_agent: str | None = None) -> bool
- seconds_left(token: str) -> int | None
- DEFAULT_SCOPES: set[str] = {"read","write","list"}
"""
from __future__ import annotations
import json, uuid, os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta, timezone

__all__ = [
    "list_agents",
    "register_agent",
    "issue_token",
    "list_active_tokens",
    "revoke_token",
    "check_token",
    "seconds_left",
    "DEFAULT_SCOPES",
]

# ---------- Storage locations ----------
HOME = Path.home()
STATE_DIR = HOME / ".agent_guard"
STATE_DIR.mkdir(parents=True, exist_ok=True)
TOKENS_PATH = STATE_DIR / "tokens_pro.json"
REGISTRY_PATH = STATE_DIR / "agents.json"  # shared with regular
AUDIT_PATH = STATE_DIR / "audit.log"

# ---------- Optional file lock ----------
try:
    from filelock import FileLock  # pip install filelock
    LOCK_PATH = STATE_DIR / ".lock"
    _LOCK = FileLock(str(LOCK_PATH))
except Exception:  # graceful fallback
    FileLock = None  # type: ignore
    _LOCK = None

# ---------- Defaults ----------
DEFAULT_SCOPES: Set[str] = {"read", "write", "list"}
DEFAULT_TTL_MIN = 30

# ---------- Time helpers ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------- IO helpers ----------

def _atomic_write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _with_lock(fn):
    if _LOCK is None:
        return fn
    def wrapper(*a, **k):
        with _LOCK:
            return fn(*a, **k)
    return wrapper


# ---------- Audit ----------
@_with_lock
def _audit(event: str, **meta):
    try:
        meta = {k: (v if isinstance(v, (str, int, float)) else str(v)) for k, v in meta.items()}
        line = json.dumps({"ts": _iso(_now()), "event": event, **meta}, ensure_ascii=False)
        with AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# ---------- Agent registry ----------

def _default_agents() -> Dict[str, Dict]:
    return {
        "Jenny": {"notes": "Core assistant"},
        "Luna": {"notes": "Social/media agent"},
        "Claude": {"notes": "External LLM"},
        "Demo": {"notes": "Hacker/cybersec agent"},
        "BobTheBuilder": {"notes": "Automation & builder"},
        "Chlo": {"notes": "Tools/dev helper"},
        "ChatGPT": {"notes": "This assistant"},
    }


@_with_lock
def _load_registry() -> Dict[str, Dict]:
    data = _load_json(REGISTRY_PATH, None)
    if data is None:
        data = _default_agents()
        _atomic_write_json(REGISTRY_PATH, data)
    return data


@_with_lock
def _save_registry(reg: Dict[str, Dict]) -> None:
    _atomic_write_json(REGISTRY_PATH, reg)


def list_agents() -> List[str]:
    return sorted(_load_registry().keys())


def register_agent(agent_name: str, notes: str = "") -> None:
    name = (agent_name or "").strip()
    if not name:
        return
    reg = _load_registry()
    reg[name] = {"notes": notes}
    _save_registry(reg)
    _audit("register_agent", agent=name)


# ---------- Tokens ----------

def _load_tokens() -> Dict[str, Dict]:
    return _load_json(TOKENS_PATH, {})


@_with_lock
def _save_tokens(tokens: Dict[str, Dict]) -> None:
    _atomic_write_json(TOKENS_PATH, tokens)


def _is_expired(info: Dict) -> bool:
    try:
        exp = datetime.fromisoformat(info["expires_at"])  # retains tz
    except Exception:
        return True
    return exp <= _now()


def _clean_expired(tokens: Dict[str, Dict]) -> Dict[str, Dict]:
    return {t: i for t, i in tokens.items() if not _is_expired(i)}


def seconds_left(token: str) -> Optional[int]:
    tokens = _load_tokens()
    info = tokens.get(token)
    if not info:
        return None
    try:
        exp = datetime.fromisoformat(info["expires_at"]).timestamp()
        left = int(exp - _now().timestamp())
        return max(left, 0)
    except Exception:
        return None


@_with_lock
def issue_token(agent: str, scopes: Optional[List[str]] = None, ttl_minutes: int = DEFAULT_TTL_MIN) -> Tuple[str, Dict]:
    reg = _load_registry()
    if agent not in reg:
        raise ValueError(f"Unknown agent '{agent}'. Register it first.")
    scopes = list(scopes or DEFAULT_SCOPES)
    if not set(scopes).issubset(DEFAULT_SCOPES):
        raise ValueError(f"Scopes must be subset of {DEFAULT_SCOPES}.")

    issued = _now()
    expires = issued + timedelta(minutes=max(1, int(ttl_minutes)))
    token = str(uuid.uuid4())
    info = {
        "agent": agent,
        "scopes": scopes,
        "issued_at": _iso(issued),
        "expires_at": _iso(expires),
        "revoked": False,
    }
    tokens = _load_tokens()
    tokens[token] = info
    tokens = _clean_expired(tokens)
    _save_tokens(tokens)
    _audit("issue_token", agent=agent, scopes=",".join(scopes), token=token, ttl_min=int(ttl_minutes))
    return token, info


@_with_lock
def revoke_token(token: str) -> bool:
    tokens = _load_tokens()
    if token in tokens:
        info = tokens[token]
        info["revoked"] = True
        _save_tokens(tokens)
        _audit("revoke_token", agent=info.get("agent"), token=token)
        return True
    return False


def list_active_tokens(agent: Optional[str] = None) -> Dict[str, Dict]:
    tokens = _clean_expired(_load_tokens())
    tokens = {t: i for t, i in tokens.items() if not i.get("revoked")}
    if agent:
        tokens = {t: i for t, i in tokens.items() if i.get("agent") == agent}
    return tokens


def check_token(token: str, needed_scope: str, expected_agent: Optional[str] = None) -> bool:
    tokens = _load_tokens()
    info = tokens.get(token)
    ok = False
    reason = "ok"
    if not info:
        reason = "missing"
    elif info.get("revoked"):
        reason = "revoked"
    elif _is_expired(info):
        # tidy: remove expired on the fly
        try:
            del tokens[token]
            _save_tokens(tokens)
        except Exception:
            pass
        reason = "expired"
    elif expected_agent and info.get("agent") != expected_agent:
        reason = "wrong_agent"
    elif needed_scope not in info.get("scopes", []):
        reason = "no_scope"
    else:
        ok = True

    _audit(
        "check_token",
        token=token,
        agent=info.get("agent") if info else None,
        need=needed_scope,
        expected=expected_agent,
        result="allow" if ok else f"deny:{reason}",
        secs_left=seconds_left(token) or 0,
    )
    return ok


# ---------- Init ----------

def ensure_defaults() -> None:
    _load_registry()
    _save_tokens(_clean_expired(_load_tokens()))

ensure_defaults()
