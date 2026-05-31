# Releasing

## Checklist

1. Run `python3 -m unittest discover -s tests -v`.
2. Run the example in dry-run mode.
3. Execute the example with explicit write approval.
4. Confirm the generated evidence contains hashes but not file content.
5. Update `CHANGELOG.md`.
6. Tag the release as `vX.Y.Z`.
7. Publish release notes from the changelog.

The GitHub release workflow packages the source archive when a version tag is
pushed.
