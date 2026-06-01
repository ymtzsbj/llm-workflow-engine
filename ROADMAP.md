# Roadmap

The roadmap favors small capabilities with visible verification over broad
automation claims.

## v0.1: Trustworthy Local Core

- [x] JSON workflow format
- [x] DAG validation
- [x] Dry-run by default
- [x] Explicit approval for file writes
- [x] Workspace path isolation
- [x] Evidence logs with content hashes
- [x] Daily brief example

## v0.2: Better Authoring

- [x] JSON Schema for editor autocomplete
- [x] Safe `init` command for starter workflows
- [x] More precise validation messages with JSON paths
- [ ] Conditional steps
- [ ] Output contracts for actions
- [x] Redaction rules for evidence metadata

## v0.3: Maintainer Workflows

- [x] Git repository read-only inspection action
- [x] Release note draft example
- [x] Maintainer guide
- [x] Issue triage draft example
- [ ] Pluggable action packages
- [ ] Action-level timeout and retry policies

## Later, After Review

- [ ] Optional OpenAI integration behind an explicit provider interface
- [ ] Human approval adapters for interactive environments
- [ ] Signed run evidence

Network access, shell execution, and publishing actions will not be added as
implicit defaults. Proposals for external side effects must include a threat
model, a least-privilege design, and tests.
