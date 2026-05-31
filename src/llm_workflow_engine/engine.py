"""Workflow execution with dry-run, approvals, and evidence logs."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .actions import ACTIONS, ActionError, sha256_text, workspace_path
from .model import Workflow, WorkflowError, WorkflowStep, validate_workflow


EXPRESSION_RE = re.compile(r"\$\{\{\s*(inputs|steps)\.([A-Za-z0-9_-]+)(?:\.output)?\s*\}\}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_string(value: str, inputs: Mapping[str, Any], outputs: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        namespace, key = match.groups()
        source: Mapping[str, Any] = inputs if namespace == "inputs" else outputs
        if key not in source:
            raise WorkflowError(f"unknown expression: {match.group(0)}")
        return str(source[key])

    return EXPRESSION_RE.sub(replace, value)


def _resolve(value: Any, inputs: Mapping[str, Any], outputs: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return _resolve_string(value, inputs, outputs)
    if isinstance(value, list):
        return [_resolve(item, inputs, outputs) for item in value]
    if isinstance(value, dict):
        return {key: _resolve(item, inputs, outputs) for key, item in value.items()}
    return value


def _planned_evidence(workspace: Path, params: Mapping[str, Any]) -> Mapping[str, Any]:
    content = params.get("content")
    path = workspace_path(workspace, params.get("path"))
    evidence: Dict[str, Any] = {"path": str(path.relative_to(workspace.resolve()))}
    if isinstance(content, str):
        evidence.update({"sha256": sha256_text(content), "bytes": len(content.encode("utf-8"))})
    return evidence


class WorkflowRunner:
    def __init__(self, workspace: Path, run_root: Path | None = None):
        self.workspace = workspace.resolve()
        self.run_root = (run_root or self.workspace / ".workflow-runs").resolve()

    def validate(self, workflow: Workflow) -> List[WorkflowStep]:
        return validate_workflow(workflow, ACTIONS)

    def plan(self, workflow: Workflow) -> List[Mapping[str, Any]]:
        ordered = self.validate(workflow)
        return [
            {
                "id": step.id,
                "uses": step.uses,
                "needs": step.needs,
                "effect": ACTIONS[step.uses].effect,
                "approval": step.approval,
            }
            for step in ordered
        ]

    def run(
        self,
        workflow: Workflow,
        *,
        overrides: Mapping[str, Any] | None = None,
        execute: bool = False,
        allow_writes: bool = False,
        approvals: Iterable[str] = (),
    ) -> Mapping[str, Any]:
        ordered = self.validate(workflow)
        inputs = dict(workflow.inputs)
        inputs.update(overrides or {})
        approved = set(approvals)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        record: Dict[str, Any] = {
            "run_id": run_id,
            "workflow": workflow.name,
            "started_at": _utc_now(),
            "mode": "execute" if execute else "dry-run",
            "status": "running",
            "steps": [],
        }
        outputs: Dict[str, str] = {}

        try:
            for step in ordered:
                params = _resolve(dict(step.params), inputs, outputs)
                action = ACTIONS[step.uses]
                step_record: Dict[str, Any] = {
                    "id": step.id,
                    "uses": step.uses,
                    "effect": action.effect,
                    "started_at": _utc_now(),
                }
                record["steps"].append(step_record)

                if action.effect == "write" and not execute:
                    step_record.update(
                        {
                            "status": "planned",
                            "evidence": _planned_evidence(self.workspace, params),
                            "finished_at": _utc_now(),
                        }
                    )
                    outputs[step.id] = str(params.get("path", ""))
                    continue

                if action.effect == "write" and not allow_writes:
                    raise ActionError(f"step {step.id} blocked: pass --allow-writes to permit file writes")
                if action.effect == "write" and step.id not in approved:
                    raise ActionError(f"step {step.id} blocked: pass --approve {step.id} to approve this write")

                result = action.run(self.workspace, params)
                outputs[step.id] = result.output
                step_record.update(
                    {"status": "completed", "evidence": dict(result.evidence), "finished_at": _utc_now()}
                )
            record["status"] = "completed"
        except (ActionError, WorkflowError) as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            if record["steps"]:
                record["steps"][-1].update({"status": "failed", "error": str(exc), "finished_at": _utc_now()})
        finally:
            record["finished_at"] = _utc_now()
            self._write_evidence(record)
        return record

    def _write_evidence(self, record: Mapping[str, Any]) -> None:
        run_dir = self.run_root / str(record["run_id"])
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "run.json").write_text(
            json.dumps(record, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
