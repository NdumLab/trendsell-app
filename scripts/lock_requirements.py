"""Regenerate backend/requirements.lock and backend/requirements-dev.lock.

Resolves the direct pins in requirements.txt / requirements-dev.txt with pip's own
resolver and writes the complete transitive set. Run from the repository root:

    python scripts/lock_requirements.py

The locks are what CI scans and what deployment installs; the .txt files stay the
human-edited source of truth for direct dependencies.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / 'backend'
HEADER = ("# Fully resolved {} dependency set, direct and transitive (action plan T09).\n"
          "# Regenerate with: python scripts/lock_requirements.py\n")


def resolve(requirements: Path) -> list[str]:
    with tempfile.NamedTemporaryFile(suffix='.json') as report:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--dry-run', '--ignore-installed',
                        '--quiet', '--report', report.name, '-r', str(requirements)], check=True)
        data = json.load(open(report.name))
    return sorted({f"{i['metadata']['name']}=={i['metadata']['version']}" for i in data['install']}, key=str.lower)


def main() -> None:
    for name, source, target in [('runtime', 'requirements.txt', 'requirements.lock'),
                                 ('development/test', 'requirements-dev.txt', 'requirements-dev.lock')]:
        pins = resolve(BACKEND / source)
        (BACKEND / target).write_text(HEADER.format(name) + '\n'.join(pins) + '\n')
        print(f'{target}: {len(pins)} pinned packages')


if __name__ == '__main__':
    main()
