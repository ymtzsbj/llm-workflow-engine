"""Command-line interface for llm-workflow-engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

from .actions import ACTIONS
from .engine import WorkflowRunner
from .model import WorkflowError, load_workflow


STARTER_SCHEMA_URL = (
    "https://raw.githubusercontent.com/ymtzsbj/llm-workflow-engine/main/schema/workflow.schema.json"
)


def _starter_workflow(name: str) -> Dict[str, Any]:
    return {
        "$schema": STARTER_SCHEMA_URL,
        "version": "1",
        "name": name,
        "description": "Render a local draft and require approval before writing it.",
        "inputs": {"focus": "Ship one small, verifiable improvement."},
        "steps": [
            {
                "id": "render_draft",
                "uses": "render_template",
                "with": {"template": "# Draft\n\n## Focus\n${{ inputs.focus }}\n"},
            },
            {
                "id": "write_draft",
                "uses": "write_text",
                "needs": ["render_draft"],
                "approval": "required",
                "with": {
                    "path": "outputs/draft.md",
                    "content": "${{ steps.render_draft.output }}",
                },
            },
        ],
    }


def _init_workflow(path: Path, *, name: str | None = None, force: bool = False) -> None:
    if path.exists() and not force:
        raise WorkflowError(f"refusing to overwrite existing file: {path}; pass --force to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    workflow_name = name or path.name.removesuffix(".workflow.json").removesuffix(".json")
    if not workflow_name:
        raise WorkflowError("workflow name cannot be empty")
    path.write_text(json.dumps(_starter_workflow(workflow_name), indent=2) + "\n", encoding="utf-8")


def _inputs(values: Iterable[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise WorkflowError(f"input override must use key=value: {value}")
        key, raw = value.split("=", 1)
        if not key:
            raise WorkflowError("input override key cannot be empty")
        result[key] = raw
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-workflow",
        description="Local-first workflow harness for reliable AI agent automation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a safe starter workflow")
    init.add_argument("workflow", type=Path)
    init.add_argument("--name", help="workflow name; defaults to the file name")
    init.add_argument("--force", action="store_true", help="replace an existing workflow file")

    validate = subparsers.add_parser("validate", help="validate a workflow definition")
    validate.add_argument("workflow", type=Path)
    validate.add_argument("--workspace", type=Path, default=Path.cwd())

    plan = subparsers.add_parser("plan", help="show ordered steps and effects")
    plan.add_argument("workflow", type=Path)
    plan.add_argument("--workspace", type=Path, default=Path.cwd())

    run = subparsers.add_parser("run", help="dry-run a workflow, or execute it explicitly")
    run.add_argument("workflow", type=Path)
    run.add_argument("--workspace", type=Path, default=Path.cwd())
    run.add_argument("--input", action="append", default=[], metavar="KEY=VALUE")
    run.add_argument("--execute", action="store_true", help="execute side effects instead of planning them")
    run.add_argument("--allow-writes", action="store_true", help="permit approved file writes")
    run.add_argument("--approve", action="append", default=[], metavar="STEP_ID")

    subparsers.add_parser("list-actions", help="show built-in actions and effects")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "init":
            _init_workflow(args.workflow, name=args.name, force=args.force)
            print(f"created: {args.workflow}")
            return 0
        if args.command == "list-actions":
            for name, action in ACTIONS.items():
                print(f"{name}\t{action.effect}")
            return 0

        workflow = load_workflow(args.workflow)
        runner = WorkflowRunner(args.workspace)
        if args.command == "validate":
            ordered = runner.validate(workflow)
            print(f"valid: {workflow.name} ({len(ordered)} steps)")
            return 0
        if args.command == "plan":
            print(json.dumps(runner.plan(workflow), indent=2))
            return 0

        record = runner.run(
            workflow,
            overrides=_inputs(args.input),
            execute=args.execute,
            allow_writes=args.allow_writes,
            approvals=args.approve,
        )
        print(json.dumps(record, indent=2))
        return 0 if record["status"] == "completed" else 1
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
