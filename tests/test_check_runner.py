"""Do not recursively invoke the suite: exercise the runner with mocks."""
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_check', ROOT / 'tools/check.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CheckRunnerTests(unittest.TestCase):
    def test_same_python_absolute_root_and_environment_preserved(self):
        old = dict(os.environ)
        with patch.object(runner.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 0)]) as run:
            self.assertEqual(runner.run_checks(), 0)
        self.assertEqual(run.call_count, 2)
        first, second = run.call_args_list
        self.assertEqual(first.args[0][0], sys.executable)
        self.assertEqual(first.kwargs['cwd'], ROOT)
        self.assertEqual(second.args[0][-1], str(ROOT / 'tools/check_publication.py'))
        self.assertEqual(first.kwargs['env']['PYTHONPATH'].split(os.pathsep)[0], str(ROOT / 'shared'))
        self.assertEqual(dict(os.environ), old)

    def test_test_failure_stops_before_publication(self):
        with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7)) as run:
            self.assertEqual(runner.run_checks(), 7)
        self.assertEqual(run.call_count, 1)

    def test_publication_failure_is_not_hidden(self):
        with patch.object(runner.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0),
                 subprocess.CompletedProcess([], 9)]):
            self.assertEqual(runner.run_checks(), 9)

    def test_help_from_outside_repository_does_not_run_tests(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/check.py'), '--help'],
                                cwd=ROOT.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Portable source-only checks', result.stdout)
        self.assertNotIn('Ran ', result.stderr)


if __name__ == '__main__':
    unittest.main()
