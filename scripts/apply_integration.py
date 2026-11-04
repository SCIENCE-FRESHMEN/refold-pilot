#!/usr/bin/env python
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Apply the extension to a clean, matching upstream checkout without publishing."""

import argparse
import json
import logging
import shutil
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Git preflight or patch application failed; inspect the checkout locally")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    repo = args.repo.resolve()
    try:
        expected = (root / "BASE_REVISION").read_text().strip()
        if git(repo, "rev-parse", "HEAD") != expected:
            raise ValueError("Base revision differs; use the documented baseline")
        if git(repo, "status", "--porcelain"):
            raise ValueError("Use a clean checkout to protect existing changes")
        paths = json.loads((root / "integration-files.json").read_text())
        for relative in paths:
            source, destination = root / relative, repo / relative
            if not source.is_file() or destination.exists():
                raise ValueError("Extension file missing or destination already exists")
        patch = root / "patches/integration.patch"
        git(repo, "apply", "--check", "--unidiff-zero", str(patch))
        for relative in paths:
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, destination)
        git(repo, "apply", "--unidiff-zero", str(patch))
        logging.info("Applied extension locally; no commit or push performed")
    except (ValueError, OSError) as exc:
        logging.error("%s", exc if not isinstance(exc, OSError) else "Required file unavailable")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
