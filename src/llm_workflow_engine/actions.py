"""Built-in actions with deliberately narrow local effects."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping


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
        if self.name == "render_issue_triage":
            return self._render_issue_triage(params)
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
    def _render_issue_triage(params: Mapping[str, Any]) -> ActionResult:
        raw_issues = params.get("issues")
        if not isinstance(raw_issues, str):
            raise ActionError("issues must be a JSON string")
        max_issues = params.get("max_issues", 100)
        if isinstance(max_issues, bool) or not isinstance(max_issues, int) or not 1 <= max_issues <= 100:
            raise ActionError("max_issues must be an integer from 1 to 100")
        try:
            export = json.loads(raw_issues)
        except json.JSONDecodeError as exc:
            raise ActionError(f"issues must contain valid JSON: {exc.msg}") from exc
        issues = export.get("issues") if isinstance(export, dict) else export
        if not isinstance(issues, list):
            raise ActionError('issues JSON must be a list or an object with an "issues" list')
        if len(issues) > max_issues:
            raise ActionError(f"issues JSON contains {len(issues)} items; max_issues is {max_issues}")

        sections: List[str] = ["# Issue triage draft", "", f"Review {len(issues)} local issue export(s)."]
        for index, issue in enumerate(issues):
            if not isinstance(issue, dict):
                raise ActionError(f"issues[{index}] must be an object")
            number = issue.get("number")
            if isinstance(number, bool) or not isinstance(number, (int, str)) or not str(number).strip():
                raise ActionError(f"issues[{index}].number must be an integer or non-empty string")
            title = issue.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ActionError(f"issues[{index}].title must be a non-empty string")
            body = issue.get("body", "")
            if not isinstance(body, str):
                raise ActionError(f"issues[{index}].body must be a string when set")
            existing_labels = issue.get("labels", [])
            if not isinstance(existing_labels, list) or not all(isinstance(label, str) for label in existing_labels):
                raise ActionError(f"issues[{index}].labels must be a list of strings when set")

            summary = " ".join(f"{title}\n{body}".lower().split())
            labels = _suggest_issue_labels(summary, existing_labels)
            priority = _suggest_issue_priority(summary)
            questions = _suggest_follow_up_questions(summary, labels)
            clean_title = " ".join(title.split())
            sections.extend(
                [
                    "",
                    f"## #{str(number).strip()}: {clean_title}",
                    "",
                    f"- Suggested priority: `{priority}`",
                    f"- Suggested labels: {', '.join(f'`{label}`' for label in labels)}",
                    "- Follow-up questions:",
                    *[f"  - {question}" for question in questions],
                ]
            )
        draft = "\n".join(sections) + "\n"
        return ActionResult(
            draft,
            {
                "sha256": sha256_text(draft),
                "bytes": len(draft.encode("utf-8")),
                "issues": len(issues),
            },
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
    "render_issue_triage": Action("render_issue_triage", "none"),
    "render_template": Action("render_template", "none"),
    "write_text": Action("write_text", "write"),
}


def _suggest_issue_labels(summary: str, existing_labels: List[str]) -> List[str]:
    labels = {label.strip().lower() for label in existing_labels if label.strip()}
    rules = {
        "bug": ("bug", "crash", "error", "fail", "regression"),
        "documentation": ("documentation", "docs", "readme"),
        "enhancement": ("enhancement", "feature", "proposal", "request"),
        "security": ("security", "vulnerability", "credential", "secret"),
    }
    for label, keywords in rules.items():
        if any(keyword in summary for keyword in keywords):
            labels.add(label)
    return sorted(labels or {"needs-triage"})


def _suggest_issue_priority(summary: str) -> str:
    if any(keyword in summary for keyword in ("security", "vulnerability", "data loss", "credential", "secret")):
        return "high"
    if any(keyword in summary for keyword in ("bug", "crash", "regression", "blocked", "fail")):
        return "medium"
    return "low"


def _suggest_follow_up_questions(summary: str, labels: List[str]) -> List[str]:
    questions: List[str] = []
    if "bug" in labels and not any(keyword in summary for keyword in ("reproduce", "reproduction", "steps")):
        questions.append("Can you provide minimal reproduction steps?")
    if "expected" not in summary:
        questions.append("What outcome did you expect?")
    if "security" in labels:
        questions.append("Should details move to the private vulnerability reporting channel?")
    if not questions:
        questions.append("Is the current description sufficient to define acceptance criteria?")
    return questions
