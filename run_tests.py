"""The one test command for this repository.

    python3 run_tests.py

Standard library only. Exit code 0 means every test passed.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(os.path.join(HERE, "tests"), top_level_dir=HERE)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print("\n%d tests, %d failures, %d errors" % (result.testsRun, len(result.failures), len(result.errors)))
    sys.exit(0 if result.wasSuccessful() else 1)
