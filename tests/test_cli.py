from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from llm_workflow_engine.cli import main


class CliTests(unittest.TestCase):
    def test_public_schema_is_valid_json_and_covers_builtin_actions(self) -> None:
        schema_path = Path(__file__).parents[1] / "schema" / "workflow.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        action_names = schema["$defs"]["step"]["properties"]["uses"]["enum"]
        self.assertEqual(["read_text", "inspect_git", "render_template", "write_text"], action_names)

    def test_init_creates_schema_aware_starter_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_path = Path(temp_dir) / "my-first.workflow.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(0, main(["init", str(workflow_path)]))
                self.assertEqual(0, main(["validate", str(workflow_path), "--workspace", temp_dir]))
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
            self.assertEqual("my-first", workflow["name"])
            self.assertTrue(workflow["$schema"].endswith("/schema/workflow.schema.json"))
            self.assertEqual("required", workflow["steps"][-1]["approval"])

    def test_init_refuses_to_overwrite_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_path = Path(temp_dir) / "workflow.json"
            workflow_path.write_text("keep me", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(2, main(["init", str(workflow_path)]))
            self.assertEqual("keep me", workflow_path.read_text(encoding="utf-8"))
            self.assertIn("refusing to overwrite", stderr.getvalue())

    def test_init_force_replaces_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_path = Path(temp_dir) / "workflow.json"
            workflow_path.write_text("replace me", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(["init", str(workflow_path), "--force"]))
            self.assertEqual("workflow", json.loads(workflow_path.read_text(encoding="utf-8"))["name"])

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
