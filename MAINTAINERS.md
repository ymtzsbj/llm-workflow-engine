# Maintainer Guide

This repository is maintained as a small, verifiable open-source workflow
engine. The maintainer workflow is deliberately visible in the repository.

## Responsibilities

- Triage reproducible bug reports and focused feature proposals.
- Review pull requests for behavior, safety boundaries, and verification.
- Keep built-in actions narrow and document every new side effect.
- Run the test suite before merging or publishing a release.
- Update `CHANGELOG.md`, tag releases, and verify the release workflow.

## Issue Triage

1. Confirm the report includes a minimal workflow or reproduction.
2. Remove or request removal of private content from public examples.
3. Label the issue as a bug, enhancement, documentation task, or security
   concern.
4. Record the expected verification command.
5. Route vulnerability reports through private reporting.

## Release Workflow

1. Run the test suite and package installation check.
2. Generate a local draft with:

   ```bash
   python3 -m llm_workflow_engine.cli run examples/release-notes.workflow.json
   ```

3. Review the repository summary and changelog.
4. Execute the draft write only when the output is ready for review:

   ```bash
   python3 -m llm_workflow_engine.cli run examples/release-notes.workflow.json \
     --execute \
     --allow-writes \
     --approve write_release_draft
   ```

5. Follow [docs/releasing.md](docs/releasing.md) before tagging the release.

## Safety Boundary

The engine may inspect local repository metadata, but it does not publish
releases, push commits, access accounts, or run arbitrary shell commands.
Those remain explicit maintainer actions outside the built-in registry.
