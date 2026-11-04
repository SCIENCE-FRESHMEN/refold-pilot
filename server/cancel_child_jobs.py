"""Cancel only jobs whose submission logs point into this reference run."""

import argparse
import os
import re
import subprocess
from pathlib import Path


def child_jobs(run: Path, root: Path) -> list[str]:
    run = run.resolve()
    if not run.is_relative_to(root.resolve() / "runs"):
        raise ValueError("Run is outside the experiment workspace")
    jobs = set()
    for log in run.glob(".nextflow.log*"):
        for line in log.read_text(errors="replace").splitlines():
            match = re.search(r"\[SLURM\].*?jobId:\s*(\d+);\s*workDir:\s*(.*?)\s*$", line)
            if match and Path(match.group(2)).resolve().is_relative_to(run / "work"):
                jobs.add(match.group(1))
    return sorted(jobs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    jobs = child_jobs(args.run, Path(os.environ["REFOLD_ROOT"]))
    if jobs:
        subprocess.run(["scancel", "--quiet", *jobs], check=False)
    print(f"CLEANUP_CHECKED_SUBMISSIONS {len(jobs)}", flush=True)
