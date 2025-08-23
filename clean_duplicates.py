#!/usr/bin/env python3
"""
Clean duplicate filename groups in a project folder.

Rules:
- Group by *filename* (ignore path). Keep ONE keeper:
  1) Prefer file in project root (if exists)
  2) Otherwise keep the most-recently modified
- Move all non-keepers to _backup_duplicates/<timestamp>/… (preserve subpath)
- Write a Markdown report to _staging_reports/duplicate_cleanup_<ts>.md
- Dry-run by default (no file moves) unless --commit is passed.

Usage:
  python3 clean_duplicates.py --root "/Users/joebudds/Documents/Updated_Relay_Files"      # dry-run
  python3 clean_duplicates.py --root "/Users/joebudds/Documents/Updated_Relay_Files" --commit
"""
import argparse, os, shutil, time
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

DEFAULT_ROOT = Path.home() / "Documents" / "Updated_Relay_Files"
SKIP_DIRS = {".git", "__pycache__", "_backup_duplicates", "_staging_reports"}
REPORT_DIR = "_staging_reports"
BACKUP_DIR = "_backup_duplicates"

def is_skipped_dir(p: Path, root: Path) -> bool:
    parts = set(p.relative_to(root).parts)
    return any(seg in SKIP_DIRS for seg in parts)

def scan_files(root: Path) -> list[Path]:
    files = []
    for p in root.rglob("*"):
        if p.is_dir():
            # Skip known noise dirs
            if p.name in SKIP_DIRS: 
                # don't descend into skipped directories
                # (rglob already descended, so we just continue)
                continue
            if is_skipped_dir(p, root): 
                continue
        else:
            if is_skipped_dir(p.parent, root):
                continue
            files.append(p)
    return files

def get_mtime_safe(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except (FileNotFoundError, OSError):
        return 0.0  # broken symlinks/missing files get lowest priority

def choose_keeper(paths: list[Path], root: Path) -> Path:
    # Filter out broken symlinks/missing files
    valid_paths = [p for p in paths if p.exists()]
    if not valid_paths:
        # If all are broken, just return the first one
        return paths[0]
    
    # 1) Prefer file at project root (i.e., path like root/filename)
    root_level = [p for p in valid_paths if p.parent == root]
    if root_level:
        return sorted(root_level, key=get_mtime_safe, reverse=True)[0]
    # 2) Else most-recently modified wins
    return sorted(valid_paths, key=get_mtime_safe, reverse=True)[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Project root folder")
    ap.add_argument("--commit", action="store_true", help="Actually move files (otherwise dry-run)")
    args = ap.parse_args()

    root: Path = args.root.resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root not found: {root}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_dir = root / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"duplicate_cleanup_{ts}.md"

    backup_base = root / BACKUP_DIR / ts
    if args.commit:
        backup_base.mkdir(parents=True, exist_ok=True)

    files = scan_files(root)
    groups = defaultdict(list)
    for f in files:
        groups[f.name].append(f)

    # Only duplicates (2+ locations of the same filename)
    dup_groups = {name: paths for name, paths in groups.items() if len(paths) > 1}

    moved = []
    kept = []
    skipped = 0

    for name, paths in sorted(dup_groups.items()):
        keeper = choose_keeper(paths, root)
        kept.append(keeper)
        for p in paths:
            if p == keeper:
                continue
            # Where to move: preserve relative path
            rel = p.relative_to(root)
            dest = backup_base / rel
            if args.commit:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dest))
            moved.append((p, dest))

    # Report
    lines = []
    lines.append(f"# Duplicate Cleanup Report — {ts}")
    lines.append("")
    lines.append(f"- Root: `{root}`")
    lines.append(f"- Mode: **{'COMMIT' if args.commit else 'DRY-RUN'}**")
    lines.append(f"- Duplicate filename groups: **{len(dup_groups)}**")
    lines.append(f"- Files moved: **{len(moved)}**")
    lines.append("")
    if dup_groups:
        lines.append("## Groups")
        for name, paths in sorted(dup_groups.items()):
            lines.append(f"### `{name}`")
            keeper = choose_keeper(paths, root)
            lines.append(f"- Keeper: `{keeper.relative_to(root)}`")
            for p in sorted(paths):
                if p == keeper:
                    continue
                dest = (backup_base / p.relative_to(root)) if args.commit else Path("<DRY-RUN>")
                lines.append(f"  - Move: `{p.relative_to(root)}` → `{dest.relative_to(root) if args.commit else dest}`")
            lines.append("")
    else:
        lines.append("_No duplicates found._")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report: {report_path}")
    if args.commit:
        print(f"Backup folder: {backup_base}")
    else:
        print("Dry-run complete. Re-run with --commit to apply changes.")

if __name__ == "__main__":
    main()