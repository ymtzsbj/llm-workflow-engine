# Releasing

## Checklist

1. Run `python3 -m unittest discover -s tests -v`.
2. Validate and dry-run every checked-in public workflow.
3. Generate the release note draft:

   ```bash
   python3 -m llm_workflow_engine.cli run examples/release-notes.workflow.json
   ```

4. Execute the release note draft write with explicit approval.
5. Confirm the generated evidence contains hashes but not file content.
6. Review the draft and update `CHANGELOG.md`.
7. Tag the release as `vX.Y.Z`.
8. Publish release notes from the changelog.

The GitHub release workflow attaches a source archive and an installable Python
wheel when a version tag is pushed.
