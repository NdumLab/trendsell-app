#!/usr/bin/env python3
"""Verify every immutable deletion-register entry and checksum."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.deletions import DeletionRegister, DeletionRegisterError  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--register-dir', required=True)
    args = parser.parse_args(argv)
    try:
        entries = DeletionRegister(args.register_dir).entries(prepare=False)
    except DeletionRegisterError as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1
    print(f'PASS: {len(entries)} durable deletion-register entries verified')
    return 0


if __name__ == '__main__':
    sys.exit(main())
