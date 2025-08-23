#!/usr/bin/env python3
"""
agent_fs_guard.py
Minimal permission guard & audit layer for my local AI agents (Jenny, Luna, Demo).
- Enforces per-agent allowed operations (read/write/network/exec).
- Enforces allowed path roots (prevents wandering outside project).
- Optional domain allowlist for network calls.
- Simple audit log of every checked action.

Usage:
    from agent_fs_guard import Guard, GuardTokenError
    guard = Guard(agent="Jenny")
    if guard.can_read("/path/file.txt"): ...
    data = guard.read_text("/path/file.txt")
    guard.write_text("/path/file.txt", "hello")
    guard.can_network("https://api.example.com")

CLI:
    python agent_fs_guard.py --test
"""
from __future__ import annotations
import os, sys, time, json, re
from pathlib import Path
from typing import Iterable, Dict, Any
from urllib.parse import urlparse

# =========================
# Custom Exceptions
# =========================

class GuardTokenError(Exception):
    """Raised when Guard token is missing, invalid, or expired."""
    pass

class GuardPermissionError(Exception):
    """Raised when Guard denies permission for an operation."""  
    pass

# ---- Policy ----
HOME = str(Path.home())
DEFAULT_AUDIT_DIR = f"{HOME}/Documents/Updated_Relay_Files"
AUDIT_LOG = Path(DEFAULT_AUDIT_DIR) / "guardian_audit.log"

POLICY: Dict[str, Dict[str, Any]] = {
    # Base defaults for any agent not explicitly listed
    "_default": {
        "allowed_ops": {"read", "write"},  # no network/exec unless granted
        "allowed_roots": [
            f"{HOME}/Documents/Updated_Relay_Files",
            f"{HOME}/Documents/AI_Relay_Files",
            f"{HOME}/Documents/demo_agent",
            f"{HOME}/Desktop",
            f"{HOME}/spark_driver_tracker",
        ],
        "denied_roots": [
            f"{HOME}/Library",  # avoid private app data
            "/System", "/bin", "/sbin", "/usr", "/etc", "/var",
        ],
        "allowed_domains": [],   # network domains allowlist (empty = none)
    },
    "Jenny": {
        "allowed_ops": {"read", "write", "network"},
        "allowed_roots": [
            f"{HOME}/Documents/Updated_Relay_Files",
            f"{HOME}/Documents/AI_Relay_Files",
            f"{HOME}/Documents/demo_agent",
            f"{HOME}/Desktop",
        ],
        "denied_roots": [],
        "allowed_domains": [
            "api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com"
        ],
    },
    "Luna": {
        "allowed_ops": {"read", "write"},
        "allowed_roots": [
            f"{HOME}/Documents/Updated_Relay_Files",
            f"{HOME}/Documents/demo_agent",
            f"{HOME}/Desktop",
        ],
        "denied_roots": [],
        "allowed_domains": [],
    },
    "Demo": {  # hacker/scan agent — NO write or network by default
        "allowed_ops": {"read"},
        "allowed_roots": [
            f"{HOME}/Documents/Updated_Relay_Files",
            f"{HOME}/Desktop",
        ],
        "denied_roots": [],
        "allowed_domains": [],
    },
}

EXCLUDES = {".git", ".venv", "__pycache__", "node_modules", ".DS_Store"}

def _resolve(p: Path) -> Path:
    try:
        return p.expanduser().resolve(strict=False)
    except Exception:
        return p.expanduser()

def _is_within(path: Path, root: Path) -> bool:
    path = _resolve(path)
    root = _resolve(root)
    return root == path or root in path.parents

def _matches_any_root(path: Path, roots: Iterable[str]) -> bool:
    return any(_is_within(path, Path(r)) for r in roots)

def _audit_write(entry: Dict[str, Any]) -> None:
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

class Guard:
    def __init__(self, agent: str = "_default"):
        self.agent = agent if agent in POLICY else "_default"
        self.policy = POLICY[self.agent]
        self.now = lambda: int(time.time())

    def _audit(self, action: str, target: str, allowed: bool, extra: Dict[str, Any] = None):
        entry = {
            "ts": self.now(),
            "agent": self.agent,
            "action": action,
            "target": target,
            "allowed": allowed,
        }
        if extra: entry.update(extra)
        _audit_write(entry)

    # ---- permission checks ----
    def _check_op(self, op: str) -> bool:
        ok = op in self.policy["allowed_ops"]
        self._audit("check_op", op, ok)
        return ok

    def _check_path(self, path: str) -> bool:
        p = Path(path)
        if any(part in EXCLUDES for part in p.parts):
            self._audit("check_path_excluded", path, False)
            return False
        allowed = _matches_any_root(p, self.policy["allowed_roots"])
        denied = _matches_any_root(p, self.policy["denied_roots"])
        ok = allowed and not denied
        self._audit("check_path", path, ok, {"allowed": allowed, "denied": denied})
        return ok

    def _check_domain(self, url: str) -> bool:
        host = urlparse(url).netloc.split(":")[0].lower()
        allowed_domains = [d.lower() for d in self.policy["allowed_domains"]]
        ok = host in allowed_domains
        self._audit("check_domain", host, ok)
        return ok

    # ---- public can_* ----
    def can_read(self, path: str) -> bool:
        return self._check_op("read") and self._check_path(path)

    def can_write(self, path: str) -> bool:
        return self._check_op("write") and self._check_path(path)

    def can_network(self, url: str) -> bool:
        return self._check_op("network") and self._check_domain(url)

    # ---- safe helpers that enforce & raise ----
    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        if not self.can_read(path):
            raise PermissionError(f"[{self.agent}] read blocked: {path}")
        return Path(path).read_text(encoding=encoding)

    def write_text(self, path: str, data: str, encoding: str = "utf-8") -> None:
        if not self.can_write(path):
            raise PermissionError(f"[{self.agent}] write blocked: {path}")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding=encoding)
        self._audit("write_text", str(p), True, {"bytes": len(data)})

# ---- very basic secret scanner helper (optional import) ----
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                  # OpenAI-like
    re.compile(r"AKIA[0-9A-Z]{16}"),                     # AWS
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),               # Google
    re.compile(r"anthropic_[a-z]{2}_[A-Za-z0-9_-]{20,}"),# Anthropic-ish
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*[\"'][^\"']+[\"']"),
]

def scan_text_for_secrets(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)

def scan_file_for_secrets(path: str) -> bool:
    try:
        data = Path(path).read_text(errors="ignore")
    except Exception:
        return False
    return scan_text_for_secrets(data)

def _self_test() -> int:
    g = Guard("Jenny")
    tmp = Path(DEFAULT_AUDIT_DIR) / "_guardian_selftest.txt"
    ok1 = g.can_read(DEFAULT_AUDIT_DIR)
    try:
        g.write_text(str(tmp), "ok")
        ok2 = True
    except Exception:
        ok2 = False
    print("read_check:", ok1, "write_check:", ok2, "audit:", AUDIT_LOG)
    return 0 if (ok1 and ok2) else 1

if __name__ == "__main__":
    # Simple CLI for quick testing
    if "--test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)