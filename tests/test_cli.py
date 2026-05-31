from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from llm_workflow_engine.cli import main


class CliTests(unittest.TestCase):
    def test_validate_and_run_dry_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            workflow_path = workspace / "workflow.json"
            workflow_path.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "name": "cli-test",
                        "steps": [
                            {
                                "id": "render",
                                "uses": "render_template",
                                "with": {"template": "hello"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(0, main(["validate", str(workflow_path), "--workspace", str(workspace)]))
                self.assertEqual(0, main(["run", str(workflow_path), "--workspace", str(workspace)]))
            self.assertIn("valid: cli-test", stdout.getvalue())
            self.assertIn('"status": "completed"', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
