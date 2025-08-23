#!/usr/bin/env python3
"""
verify_relay_project.py
Quick integrity pass over my Relay/agents repo(s):
- Finds Python syntax errors
- Flags duplicate-ish filenames
- Scans for likely secrets
- Notes TODO/FIXME
- Writes a markdown report

Run:
  python3 verify_relay_project.py --hours 12
"""
import argparse, os, sys, json, re, py_compile, time
from pathlib import Path
from collections import defaultdict

HOME = str(Path.home())
DEFAULT_ROOTS = [
    f"{HOME}/Documents/Updated_Relay_Files",
    f"{HOME}/Documents/AI_Relay_Files",
    f"{HOME}/Documents/demo_agent",
    f"{HOME}/Desktop",
    f"{HOME}/spark_driver_tracker",
]
EXCLUDES = {".git", ".venv", "__pycache__", "node_modules", ".DS_Store"}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*[\"'][^\"']+[\"']"),
]

def recent_enough(p: Path, threshold: float) -> bool:
    try:
        return p.stat().st_mtime >= threshold
    except Exception:
        return False

def iter_files(root: Path, threshold: float):
    for p in root.rglob("*"):
        if p.is_dir():
            if p.name in EXCLUDES: continue
            if any(part in EXCLUDES for part in p.parts): continue
            continue
        if any(part in EXCLUDES for part in p.parts): continue
        if not recent_enough(p, threshold): continue
        yield p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS)
    ap.add_argument("--hours", type=float, default=6.0)
    ap.add_argument("--outdir", default=f"{HOME}/Documents/Updated_Relay_Files/_staging_reports")
    args = ap.parse_args()

    now = time.time()
    threshold = now - args.hours * 3600
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    report = {
        "scanned_roots": args.roots,
        "hours_back": args.hours,
        "started": int(now),
        "py_syntax_errors": [],
        "duplicates": [],
        "secrets": [],
        "todos": [],
        "summary": {},
    }

    # gather candidates
    files = []
    for r in args.roots:
        rp = Path(r).expanduser()
        if rp.exists():
            files.extend(list(iter_files(rp, threshold)))

    # syntax check + collect metadata
    name_map = defaultdict(list)
    todos = []
    secrets = []
    py_errors = []

    for f in files:
        name_map[f.name.lower()].append(str(f))
        # syntax on .py
        if f.suffix == ".py":
            try:
                py_compile.compile(str(f), doraise=True)
            except py_compile.PyCompileError as e:
                py_errors.append({"file": str(f), "error": str(e)})

        # scan for TODO/FIXME and secrets (lightweight)
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            text = ""
        if "TODO" in text or "FIXME" in text:
            todos.append(str(f))
        if any(p.search(text) for p in SECRET_PATTERNS):
            secrets.append(str(f))

    # duplicates
    dups = []
    for name, paths in name_map.items():
        if len(paths) > 1:
            dups.append({"name": name, "paths": paths})

    report["py_syntax_errors"] = py_errors
    report["duplicates"] = dups
    report["secrets"] = secrets
    report["todos"] = todos
    report["summary"] = {
        "total_files_scanned": len(files),
        "py_files": sum(1 for f in files if f.suffix == ".py"),
        "syntax_error_count": len(py_errors),
        "duplicate_name_groups": len(dups),
        "secret_hits": len(secrets),
        "todo_files": len(todos),
    }

    # write markdown
    md = outdir / "relay_integrity_report.md"
    with open(md, "w") as f:
        f.write(f"# Relay Integrity Report\n\n")
        f.write(f"- Hours back: **{args.hours}**\n")
        f.write(f"- Roots: {', '.join(args.roots)}\n")
        f.write(f"- Files scanned: **{report['summary']['total_files_scanned']}**\n")
        f.write(f"- Python files: **{report['summary']['py_files']}**\n")
        f.write(f"- Syntax errors: **{report['summary']['syntax_error_count']}**\n")
        f.write(f"- Duplicate name groups: **{report['summary']['duplicate_name_groups']}**\n")
        f.write(f"- Secret hits: **{report['summary']['secret_hits']}**\n")
        f.write(f"- Files w/ TODOs: **{report['summary']['todo_files']}**\n\n")

        if py_errors:
            f.write("## Python Syntax Errors\n")
            for e in py_errors:
                f.write(f"- `{e['file']}`\n\n```\n{e['error']}\n```\n\n")
        if dups:
            f.write("## Duplicate-ish Filenames\n")
            for g in dups:
                f.write(f"- **{g['name']}**\n")
                for p in g["paths"]:
                    f.write(f"  - {p}\n")
        if secrets:
            f.write("\n## Possible Secrets (review/remove)\n")
            for s in secrets:
                f.write(f"- {s}\n")
        if todos:
            f.write("\n## TODO / FIXME Locations\n")
            for t in todos:
                f.write(f"- {t}\n")

    print(f"Wrote report: {md}")
    return 0

if __name__ == "__main__":
    sys.exit(main())