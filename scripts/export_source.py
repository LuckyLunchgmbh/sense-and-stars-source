#!/usr/bin/env python3
"""Export complete application sources without internal project administration.

Only explicit application paths are eligible. This operates on tracked files,
never traverses ignored data directories, rejects symlinks and never overwrites
an existing destination. It performs no GitHub or deployment operation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "LICENSE", "THIRD_PARTY_NOTICES.md", ".gitignore", ".vercelignore",
    ".env.example", ".python-version", "pyproject.toml", "requirements.txt",
    "uv.lock", "vercel.json",
}
PREFIXES = ("api/", "backend/", "frontend/", "scripts/", ".github/", "release/")


def export(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Destination already exists; no files overwritten.")
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode().split("\0")
    paths = sorted(p for p in tracked if p and (p in FILES or p.startswith(PREFIXES)))
    for required in ("LICENSE", "THIRD_PARTY_NOTICES.md", "release/README.source.md"):
        if required not in paths:
            raise ValueError(f"Required tracked source missing: {required}")
    for name in paths:
        p = ROOT / name
        if p.is_symlink() or not p.is_file():
            raise ValueError(f"Source must be a regular file: {name}")
        if any(part in {"node_modules", "__pycache__", ".venv", "dist"} for part in p.relative_to(ROOT).parts):
            raise ValueError(f"Generated content cannot be exported: {name}")
    destination.mkdir(parents=True)
    manifest = {}
    for name in paths:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
        manifest[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    shutil.copy2(ROOT / "release/README.source.md", destination / "README.md")
    manifest["README.md"] = hashlib.sha256((destination / "README.md").read_bytes()).hexdigest()
    (destination / "SOURCE-MANIFEST.json").write_text(
        json.dumps({"format": 1, "files": manifest}, indent=2, sort_keys=True) + "\n"
    )
    return len(manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    args = parser.parse_args()
    print(f"Exported {export(args.destination)} application source files.")
