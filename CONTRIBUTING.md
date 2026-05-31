# Contributing

Thanks for helping improve `llm-workflow-engine`.

## Development Setup

The core has no runtime dependencies.

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
python3 -m llm_workflow_engine.cli validate examples/daily-brief.workflow.json
python3 -m llm_workflow_engine.cli run examples/daily-brief.workflow.json
```

## Pull Requests

Keep changes small and explain:

1. the workflow problem being solved;
2. the safety boundary affected by the change;
3. the verification command and expected evidence;
4. whether the change adds a new side effect.

New actions must include tests for path boundaries, approval behavior, and
evidence metadata where applicable.

## Issues

Use the issue templates for bugs and feature proposals. Security issues should
follow [SECURITY.md](SECURITY.md).

## Release Process

Releases follow [docs/releasing.md](docs/releasing.md). A release should only
be tagged after the test suite passes and the changelog matches the shipped
behavior.
