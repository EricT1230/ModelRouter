#!/usr/bin/env python3
"""Run repository regressions, rejecting successful discovery of zero tests."""
import argparse
import sys
import unittest
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-dir', default=str(Path(__file__).resolve().parents[1] / 'tests'))
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(args.start_dir)
    if suite.countTestCases() == 0:
        print('ZERO_TESTS: regression verification cannot pass without tests')
        return 2
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
