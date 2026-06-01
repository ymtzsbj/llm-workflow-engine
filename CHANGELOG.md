# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed

- Added a 60-second release-wheel first-run path and separated contributor
  setup from the install experience.
- Future GitHub releases attach an installable wheel alongside the source
  archive, and CI validates and dry-runs every checked-in public workflow.

## [0.4.0] - 2026-06-01

### Added

- Deterministic `render_issue_triage` action for converting local JSON issue
  exports into reviewable priority, label, and follow-up question suggestions.
- Read-only issue triage draft example with a small sanitized fixture.
- Opt-in workflow-level evidence metadata redaction for logged paths and
  failure messages while preserving hashes and byte sizes.

## [0.3.0] - 2026-06-01

### Added

- Read-only `inspect_git` action for local maintainer workflows.
- Release note draft example that summarizes repository state before requiring
  explicit approval for the local draft write.
- Maintainer guide with the release and issue-triage responsibilities used by
  this project.

## [0.2.0] - 2026-05-31

### Added

- JSON Schema for workflow editor autocomplete and static validation.
- `llm-workflow init` command for creating a safe starter workflow.

### Changed

- Validation errors now include JSON-style paths for faster authoring feedback.
- The daily brief example declares the public workflow schema.

## [0.1.0] - 2026-05-31

### Added

- Dependency-free Python CLI with `validate`, `plan`, `run`, and
  `list-actions` commands.
- JSON workflow parsing and DAG validation.
- Local built-in actions: `read_text`, `render_template`, and `write_text`.
- Dry-run execution, explicit approval gates, workspace path isolation, and
  SHA-256 run evidence.
- Daily brief example, tests, CI, and maintainer documentation.
