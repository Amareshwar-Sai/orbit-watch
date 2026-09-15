"""Exercise the actual CLI and persisted database, not only internal functions."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orbitwatch.core import ROOT


class CLITests(unittest.TestCase):
    def test_review_export_backup_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.db"
            output = Path(tmp) / "approved.md"
            backup = Path(tmp) / "backup.db"

            def run(*args, database_path=db):
                return subprocess.run([sys.executable, "-m", "orbitwatch", "--db", str(database_path), *args],
                                      cwd=ROOT, text=True, capture_output=True, timeout=15)

            self.assertEqual(run("seed").returncode, 0)
            self.assertEqual(run("article", "ka-sat-2022", "--approved-only").returncode, 1)
            result = run("review", "ka-sat-2022", "--version", "1", "--decision", "approved",
                         "--reviewer", "Test reviewer", "--note", "CLI fixture review")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(run("article", "ka-sat-2022", "--approved-only", "--output", str(output)).returncode, 0)
            original = output.read_bytes()
            self.assertIn(b"APPROVED", original)
            self.assertEqual(run("article", "ka-sat-2022", "--output", str(output)).returncode, 1)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(run("backup", str(backup)).returncode, 0)
            self.assertIn("approved", run("list", database_path=backup).stdout)
            self.assertEqual(run("backup", str(backup)).returncode, 1)


if __name__ == "__main__":
    unittest.main()
