#!/usr/bin/env python3
"""Apply an audited single-GPU resource profile to this project's pending work."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def adjusted_arguments(arguments: list[str], root: Path, profile: dict, cwd: Path) -> tuple[list[str], str | None]:
    features = profile.get('gpu_features', '')
    if profile.get('gpu_mode') == 'auto' and not re.fullmatch(r'[A-Za-z0-9_|.-]+', features):
        raise ValueError('Invalid GPU feature profile')
    for argument in arguments:
        candidate = (cwd / argument).resolve()
        if candidate.name != '.command.run' or not candidate.is_file() or not candidate.is_relative_to(root.resolve() / 'runs'):
            continue
        text = candidate.read_text()
        run = candidate.relative_to(root.resolve() / 'runs').parts[0]
        if run in profile.get('frozen_generation_runs', []):
            process = re.search(r"^### name: '([^']+)'", text, re.MULTILINE)
            if not process:
                raise ValueError('A frozen run requires a known process identity')
            stage = process.group(1).split(' (')[0].split(':')[-1]
            if stage in {'RFDIFFUSION', 'DL_BINDER_DESIGN_PROTEINMPNN', 'AF2_INITIAL_GUESS'}:
                raise ValueError('Frozen reference pool forbids a generation cache miss')
        if profile.get('gpu_mode') != 'auto':
            return arguments, None
        match = re.search(r'^#SBATCH[^\n]*--gres[ =](gpu(?::[^\s]+)?)', text, re.MULTILINE)
        if not match:
            return arguments, None
        if match.group(1).split(':')[-1] != '1':
            raise ValueError('Resource adaptation requires a single-GPU request')
        return ['--gres=gpu:1', '--constraint=' + features, *arguments], candidate.relative_to(root.resolve()).as_posix()
    return arguments, None


def main() -> None:
    root = Path(os.environ.get('REFOLD_ROOT', Path(__file__).resolve().parents[1])).resolve()
    profile = json.loads((root / 'runtime/scheduler-profile.private.json').read_text())
    real = Path(profile['real_sbatch'])
    if real.name != 'sbatch' or not real.is_file() or real.resolve() == Path(__file__).resolve():
        raise ValueError('Original scheduler command is unavailable')
    arguments, script = adjusted_arguments(sys.argv[1:], root, profile, Path.cwd())
    if script:
        record = {'script': script, 'gpu_request': 'gpu:1', 'features': profile['gpu_features'],
                  'test_only': '--test-only' in arguments}
        with (root / 'runtime/sbatch-adjustments.private.jsonl').open('a') as handle:
            handle.write(json.dumps(record) + '\n')
    os.execv(str(real), [str(real), *arguments])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print('Scheduler resource adaptation failed: ' + str(error), file=sys.stderr)
        raise SystemExit(2) from error
