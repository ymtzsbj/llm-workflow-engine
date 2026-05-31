from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm_workflow_engine.actions import ActionError, workspace_path
from llm_workflow_engine.engine import WorkflowRunner
from llm_workflow_engine.model import Workflow, WorkflowError, WorkflowStep, validate_workflow


def workflow_for(*steps: WorkflowStep) -> Workflow:
    return Workflow("1", "test", "", {"focus": "verify"}, list(steps))


class WorkflowValidationTests(unittest.TestCase):
    def test_orders_dependencies(self) -> None:
        workflow = workflow_for(
            WorkflowStep("write", "write_text", {"path": "out.md", "content": "ok"}, ["render"], "required"),
            WorkflowStep("render", "render_template", {"template": "ok"}),
        )
        ordered = validate_workflow(workflow, {"render_template", "write_text"})
        self.assertEqual(["render", "write"], [step.id for step in ordered])

    def test_rejects_dependency_cycle(self) -> None:
        workflow = workflow_for(
            WorkflowStep("one", "render_template", {"template": "1"}, ["two"]),
            WorkflowStep("two", "render_template", {"template": "2"}, ["one"]),
        )
        with self.assertRaisesRegex(WorkflowError, "dependency cycle"):
            validate_workflow(workflow, {"render_template"})

    def test_write_step_requires_declared_approval(self) -> None:
        workflow = workflow_for(WorkflowStep("write", "write_text", {"path": "out.md", "content": "ok"}))
        with self.assertRaisesRegex(WorkflowError, "approval"):
            validate_workflow(workflow, {"write_text"})


class WorkflowExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        (self.workspace / "input.md").write_text("dashboard", encoding="utf-8")
        self.workflow = workflow_for(
            WorkflowStep("read", "read_text", {"path": "input.md"}),
            WorkflowStep(
                "render",
                "render_template",
                {"template": "# Brief\n${{ steps.read.output }}\n${{ inputs.focus }}\n"},
                ["read"],
            ),
            WorkflowStep(
                "write",
                "write_text",
                {"path": "outputs/brief.md", "content": "${{ steps.render.output }}"},
                ["render"],
                "required",
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_dry_run_does_not_write_output(self) -> None:
        record = WorkflowRunner(self.workspace).run(self.workflow)
        self.assertEqual("completed", record["status"])
        self.assertEqual("planned", record["steps"][-1]["status"])
        self.assertFalse((self.workspace / "outputs/brief.md").exists())

    def test_execute_blocks_unapproved_write(self) -> None:
        record = WorkflowRunner(self.workspace).run(self.workflow, execute=True, allow_writes=True)
        self.assertEqual("failed", record["status"])
        self.assertIn("--approve write", record["error"])
        self.assertFalse((self.workspace / "outputs/brief.md").exists())

    def test_execute_writes_after_explicit_approval(self) -> None:
        record = WorkflowRunner(self.workspace).run(
            self.workflow,
            execute=True,
            allow_writes=True,
            approvals={"write"},
        )
        self.assertEqual("completed", record["status"])
        self.assertEqual("# Brief\ndashboard\nverify\n", (self.workspace / "outputs/brief.md").read_text())
        evidence = record["steps"][-1]["evidence"]
        self.assertEqual("outputs/brief.md", evidence["path"])
        self.assertNotIn("content", evidence)

    def test_evidence_file_excludes_rendered_content(self) -> None:
        record = WorkflowRunner(self.workspace).run(self.workflow)
        evidence_path = self.workspace / ".workflow-runs" / record["run_id"] / "run.json"
        contents = evidence_path.read_text(encoding="utf-8")
        self.assertNotIn("dashboard", contents)
        self.assertIn('"sha256"', contents)

    def test_rejects_path_escape(self) -> None:
        with self.assertRaisesRegex(ActionError, "escapes workspace"):
            workspace_path(self.workspace, "../secret.md")


if __name__ == "__main__":
    unittest.main()
