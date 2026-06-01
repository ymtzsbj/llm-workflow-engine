from __future__ import annotations

import tempfile
import subprocess
import unittest
from pathlib import Path

from llm_workflow_engine.actions import ACTIONS, ActionError, sha256_text, workspace_path
from llm_workflow_engine.engine import WorkflowRunner
from llm_workflow_engine.model import Workflow, WorkflowError, WorkflowStep, load_workflow, validate_workflow


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

    def test_rejects_invalid_programmatic_evidence_redaction(self) -> None:
        workflow = Workflow("1", "test", "", {}, [WorkflowStep("render", "render_template")], [""])
        with self.assertRaisesRegex(WorkflowError, "evidence_redact"):
            validate_workflow(workflow, {"render_template"})


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

    def test_evidence_redacts_completed_path_without_changing_hash(self) -> None:
        workflow = Workflow(
            "1",
            "redacted-write",
            "",
            {},
            [WorkflowStep("write", "write_text", {"path": "private/client/brief.md", "content": "ok"}, [], "required")],
            ["private/client"],
        )
        record = WorkflowRunner(self.workspace).run(
            workflow,
            execute=True,
            allow_writes=True,
            approvals={"write"},
        )
        evidence = record["steps"][0]["evidence"]
        self.assertEqual("[REDACTED]/brief.md", evidence["path"])
        self.assertEqual(sha256_text("ok"), evidence["sha256"])
        self.assertEqual(2, evidence["bytes"])
        self.assertEqual("ok", (self.workspace / "private" / "client" / "brief.md").read_text(encoding="utf-8"))

    def test_evidence_redacts_failed_path_in_returned_record_and_log(self) -> None:
        workflow = Workflow(
            "1",
            "redacted-failure",
            "",
            {},
            [WorkflowStep("read", "read_text", {"path": "private/client/missing.md"})],
            ["private/client"],
        )
        record = WorkflowRunner(self.workspace).run(workflow)
        evidence_path = self.workspace / ".workflow-runs" / record["run_id"] / "run.json"
        contents = evidence_path.read_text(encoding="utf-8")
        self.assertEqual("failed", record["status"])
        self.assertIn("[REDACTED]/missing.md", record["error"])
        self.assertNotIn("private/client", record["error"])
        self.assertIn("[REDACTED]/missing.md", contents)
        self.assertNotIn("private/client", contents)

    def test_rejects_path_escape(self) -> None:
        with self.assertRaisesRegex(ActionError, "escapes workspace"):
            workspace_path(self.workspace, "../secret.md")

    def test_inspect_git_returns_read_only_repository_summary(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "add", "input.md"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "add dashboard"], check=True)
        result = ACTIONS["inspect_git"].run(self.workspace, {"path": ".", "max_commits": 3})
        self.assertIn("Working tree: clean", result.output)
        self.assertIn("- ", result.output)
        self.assertIn("add dashboard", result.output)
        self.assertEqual(0, result.evidence["dirty_paths"])
        self.assertEqual("dashboard", (self.workspace / "input.md").read_text(encoding="utf-8"))

    def test_inspect_git_rejects_path_escape(self) -> None:
        with self.assertRaisesRegex(ActionError, "escapes workspace"):
            ACTIONS["inspect_git"].run(self.workspace, {"path": ".."})

    def test_inspect_git_rejects_unbounded_commit_count(self) -> None:
        with self.assertRaisesRegex(ActionError, "max_commits"):
            ACTIONS["inspect_git"].run(self.workspace, {"max_commits": 1000})


class IssueTriageExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        repository = Path(__file__).parents[1]
        fixture = repository / "examples" / "fixtures" / "issues.json"
        fixture_target = self.workspace / "examples" / "fixtures" / "issues.json"
        fixture_target.parent.mkdir(parents=True)
        fixture_target.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
        self.workflow = load_workflow(repository / "examples" / "issue-triage.workflow.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_dry_run_plans_triage_draft_without_writing(self) -> None:
        record = WorkflowRunner(self.workspace).run(self.workflow)
        self.assertEqual("completed", record["status"])
        self.assertEqual(["completed", "completed", "planned"], [step["status"] for step in record["steps"]])
        self.assertEqual("[REDACTED]/issues.json", record["steps"][0]["evidence"]["path"])
        self.assertEqual(3, record["steps"][1]["evidence"]["issues"])
        self.assertFalse((self.workspace / "drafts" / "issue-triage.md").exists())

    def test_execute_blocks_triage_draft_without_approval(self) -> None:
        record = WorkflowRunner(self.workspace).run(self.workflow, execute=True, allow_writes=True)
        self.assertEqual("failed", record["status"])
        self.assertIn("--approve write_triage_draft", record["error"])
        self.assertFalse((self.workspace / "drafts" / "issue-triage.md").exists())

    def test_evidence_excludes_issue_titles_and_rendered_draft(self) -> None:
        record = WorkflowRunner(self.workspace).run(self.workflow)
        evidence_path = self.workspace / ".workflow-runs" / record["run_id"] / "run.json"
        contents = evidence_path.read_text(encoding="utf-8")
        self.assertNotIn("CLI crashes", contents)
        self.assertNotIn("leaked credential", contents)
        self.assertIn('"issues": 3', contents)

    def test_execute_writes_triage_draft_after_explicit_approval(self) -> None:
        record = WorkflowRunner(self.workspace).run(
            self.workflow,
            execute=True,
            allow_writes=True,
            approvals={"write_triage_draft"},
        )
        self.assertEqual("completed", record["status"])
        draft = (self.workspace / "drafts" / "issue-triage.md").read_text(encoding="utf-8")
        self.assertIn("## #17: CLI crashes", draft)
        self.assertIn("- Suggested priority: `medium`", draft)
        self.assertIn("- Suggested labels: `bug`", draft)
        self.assertIn("Should details move to the private vulnerability reporting channel?", draft)

    def test_rejects_issue_export_path_escape(self) -> None:
        record = WorkflowRunner(self.workspace).run(
            self.workflow,
            overrides={"issue_export": "../secret.json"},
        )
        self.assertEqual("failed", record["status"])
        self.assertIn("path escapes workspace", record["error"])

    def test_rejects_invalid_issue_export_json(self) -> None:
        with self.assertRaisesRegex(ActionError, "valid JSON"):
            ACTIONS["render_issue_triage"].run(self.workspace, {"issues": "not-json"})


if __name__ == "__main__":
    unittest.main()
