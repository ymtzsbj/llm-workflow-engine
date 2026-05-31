"""Built-in actions with deliberately narrow local effects."""

from __future__ import annotations

import hashlib
import subprocess
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
        if self.name == "inspect_git":
            return self._inspect_git(workspace, params)
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
    def _inspect_git(workspace: Path, params: Mapping[str, Any]) -> ActionResult:
        repo = workspace_path(workspace, params.get("path", "."))
        max_commits = params.get("max_commits", 5)
        if isinstance(max_commits, bool) or not isinstance(max_commits, int) or not 1 <= max_commits <= 50:
            raise ActionError("max_commits must be an integer from 1 to 50")

        def git(*args: str) -> str:
            try:
                result = subprocess.run(
                    ["git", "-C", str(repo), *args],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except FileNotFoundError as exc:
                raise ActionError("git executable not found") from exc
            except subprocess.TimeoutExpired as exc:
                raise ActionError(f"git inspection timed out for {repo}") from exc
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.strip() or exc.stdout.strip() or "git command failed"
                raise ActionError(f"cannot inspect git repository {repo}: {detail}") from exc
            return result.stdout.strip()

        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        status = git("status", "--porcelain=v1")
        tags = git("tag", "--sort=-creatordate")
        commits = git("log", f"--max-count={max_commits}", "--pretty=format:%h %s")
        dirty_paths = [line for line in status.splitlines() if line]
        tag_names = [line for line in tags.splitlines() if line][:10]
        commit_lines = [line for line in commits.splitlines() if line]
        summary = "\n".join(
            [
                f"Repository: {repo.relative_to(workspace.resolve()) or Path('.')}",
                f"Branch: {branch}",
                f"Working tree: {'clean' if not dirty_paths else f'{len(dirty_paths)} changed path(s)'}",
                f"Tags: {', '.join(tag_names) if tag_names else 'none'}",
                "Recent commits:",
                *[f"- {line}" for line in commit_lines],
            ]
        )
        return ActionResult(
            summary,
            {
                "path": str(repo.relative_to(workspace.resolve()) or Path(".")),
                "sha256": sha256_text(summary),
                "bytes": len(summary.encode("utf-8")),
                "branch": branch,
                "dirty_paths": len(dirty_paths),
                "tags": len(tag_names),
                "commits": len(commit_lines),
            },
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
    "inspect_git": Action("inspect_git", "read"),
    "render_template": Action("render_template", "none"),
    "write_text": Action("write_text", "write"),
}
