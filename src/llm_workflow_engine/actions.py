"""Built-in actions with deliberately narrow local effects."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping


class ActionError(RuntimeError):
    """Raised when an action cannot complete safely."""


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def workspace_path(workspace: Path, raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ActionError("path must be a non-empty string")
    root = workspace.resolve()
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ActionError(f"path escapes workspace: {raw_path}") from exc
    return candidate


@dataclass(frozen=True)
class ActionResult:
    output: str
    evidence: Mapping[str, Any]


@dataclass(frozen=True)
class Action:
    name: str
    effect: str

    def run(self, workspace: Path, params: Mapping[str, Any]) -> ActionResult:
        if self.name == "read_text":
            return self._read_text(workspace, params)
        if self.name == "render_template":
            return self._render_template(params)
        if self.name == "write_text":
            return self._write_text(workspace, params)
        raise ActionError(f"unsupported action: {self.name}")

    @staticmethod
    def _read_text(workspace: Path, params: Mapping[str, Any]) -> ActionResult:
        path = workspace_path(workspace, params.get("path"))
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ActionError(f"cannot read {path}: {exc}") from exc
        return ActionResult(
            content,
            {
                "path": str(path.relative_to(workspace.resolve())),
                "sha256": sha256_text(content),
                "bytes": len(content.encode("utf-8")),
            },
        )

    @staticmethod
    def _render_template(params: Mapping[str, Any]) -> ActionResult:
        template = params.get("template")
        if not isinstance(template, str):
            raise ActionError("template must be a string")
        return ActionResult(
            template,
            {"sha256": sha256_text(template), "bytes": len(template.encode("utf-8"))},
        )

    @staticmethod
    def _write_text(workspace: Path, params: Mapping[str, Any]) -> ActionResult:
        path = workspace_path(workspace, params.get("path"))
        content = params.get("content")
        if not isinstance(content, str):
            raise ActionError("content must be a string")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ActionResult(
            str(path.relative_to(workspace.resolve())),
            {
                "path": str(path.relative_to(workspace.resolve())),
                "sha256": sha256_text(content),
                "bytes": len(content.encode("utf-8")),
            },
        )


ACTIONS: Dict[str, Action] = {
    "read_text": Action("read_text", "read"),
    "render_template": Action("render_template", "none"),
    "write_text": Action("write_text", "write"),
}
