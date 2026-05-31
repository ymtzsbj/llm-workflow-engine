"""Workflow parsing and validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


class WorkflowError(ValueError):
    """Raised when a workflow definition is invalid."""


STEP_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    uses: str
    params: Mapping[str, Any] = field(default_factory=dict)
    needs: List[str] = field(default_factory=list)
    approval: str | None = None


@dataclass(frozen=True)
class Workflow:
    version: str
    name: str
    description: str
    inputs: Mapping[str, Any]
    steps: List[WorkflowStep]


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} must be an object")
    return value


def load_workflow(path: Path) -> Workflow:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"workflow file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON at line {exc.lineno}, column {exc.colno}") from exc

    data = _require_mapping(raw, "$")
    version = data.get("version")
    if version != "1":
        raise WorkflowError('$.version must be "1"')

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WorkflowError("$.name must be a non-empty string")

    description = data.get("description", "")
    if not isinstance(description, str):
        raise WorkflowError("$.description must be a string")

    inputs = _require_mapping(data.get("inputs", {}), "$.inputs")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowError("$.steps must be a non-empty list")

    steps: List[WorkflowStep] = []
    for index, raw_step in enumerate(raw_steps):
        step_path = f"$.steps[{index}]"
        step = _require_mapping(raw_step, step_path)
        step_id = step.get("id")
        if not isinstance(step_id, str) or not STEP_ID_RE.match(step_id):
            raise WorkflowError(f"{step_path}.id must match {STEP_ID_RE.pattern}")
        uses = step.get("uses")
        if not isinstance(uses, str) or not uses:
            raise WorkflowError(f"{step_path}.uses must be a non-empty string")
        params = _require_mapping(step.get("with", {}), f"{step_path}.with")
        needs = step.get("needs", [])
        if not isinstance(needs, list) or not all(isinstance(item, str) for item in needs):
            raise WorkflowError(f"{step_path}.needs must be a list of step ids")
        approval = step.get("approval")
        if approval not in (None, "required"):
            raise WorkflowError(f'{step_path}.approval must be "required" when set')
        steps.append(WorkflowStep(step_id, uses, params, needs, approval))

    return Workflow(version, name, description, inputs, steps)


def validate_workflow(workflow: Workflow, action_names: Iterable[str]) -> List[WorkflowStep]:
    known_actions = set(action_names)
    by_id: Dict[str, WorkflowStep] = {}
    for step in workflow.steps:
        if step.id in by_id:
            raise WorkflowError(f"duplicate step id: {step.id}")
        if step.uses not in known_actions:
            raise WorkflowError(f"step {step.id} uses unknown action: {step.uses}")
        if step.uses == "write_text" and step.approval != "required":
            raise WorkflowError(f"step {step.id} must declare approval: required")
        by_id[step.id] = step

    for step in workflow.steps:
        for dependency in step.needs:
            if dependency not in by_id:
                raise WorkflowError(f"step {step.id} needs unknown step: {dependency}")
            if dependency == step.id:
                raise WorkflowError(f"step {step.id} cannot depend on itself")

    ordered: List[WorkflowStep] = []
    remaining = list(workflow.steps)
    completed = set()
    while remaining:
        ready = [step for step in remaining if set(step.needs) <= completed]
        if not ready:
            blocked = ", ".join(step.id for step in remaining)
            raise WorkflowError(f"workflow contains a dependency cycle involving: {blocked}")
        for step in ready:
            ordered.append(step)
            completed.add(step.id)
            remaining.remove(step)
    return ordered
