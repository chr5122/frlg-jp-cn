"""Portable source-only checks: synthetic tests followed by publication audit.

Run from any directory. Uses the active Python, no make/pip/network/game files.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_checks(root: Path = ROOT) -> int:
    env = dict(os.environ)
    shared = str(root / 'shared')
    env['PYTHONPATH'] = shared + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    commands = [
        [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
        [sys.executable, '-B', str(root / 'tools/check_publication.py')],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=root, env=env)
        if result.returncode != 0:
            return result.returncode
    return 0


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    return run_checks()


if __name__ == '__main__':
    sys.exit(main())
