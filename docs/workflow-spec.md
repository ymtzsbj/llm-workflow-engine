# Workflow Specification v1

A workflow is a JSON object with a name, optional default inputs, and an
ordered list of steps.

Create a schema-aware starter file with:

```bash
llm-workflow init my-first.workflow.json
```

The command refuses to overwrite an existing file unless `--force` is
provided. The public JSON Schema lives at
[`schema/workflow.schema.json`](../schema/workflow.schema.json).

## Top-Level Fields

| Field | Required | Description |
| --- | --- | --- |
| `$schema` | no | URL or path for editor autocomplete and static validation. |
| `version` | yes | Must be `"1"`. |
| `name` | yes | Human-readable workflow name. |
| `description` | no | Short explanation of the workflow. |
| `inputs` | no | Default scalar input values. |
| `steps` | yes | Non-empty list of workflow steps. |

## Step Fields

| Field | Required | Description |
| --- | --- | --- |
| `id` | yes | Unique identifier using letters, digits, `_`, or `-`. |
| `uses` | yes | Built-in action name. |
| `with` | no | Action parameters. |
| `needs` | no | List of step IDs that must complete first. |
| `approval` | for writes | Must be `"required"` for `write_text`. |

## Expressions

String parameters may reference inputs and step outputs:

```text
${{ inputs.focus }}
${{ steps.read_dashboard.output }}
```

Expressions are resolved immediately before each step runs.

## Built-In Actions

### `read_text`

Reads a UTF-8 text file within the selected workspace.

```json
{"path": "notes/Dashboard.md"}
```

### `render_template`

Returns the resolved template string. Expressions may appear in `template`.

```json
{"template": "# Brief\n${{ inputs.focus }}\n"}
```

### `render_issue_triage`

Parses a local JSON issue export and renders a Markdown triage draft with
deterministic suggestions for priority, labels, and follow-up questions. It
does not call a remote API or update issues. The JSON value may be a list of
issues or an object with an `issues` list. Each issue must include `number` and
`title`; `body` and `labels` are optional.

```json
{"issues": "${{ steps.read_issue_export.output }}", "max_issues": 100}
```

### `inspect_git`

Runs a fixed set of read-only Git commands against a repository inside the
selected workspace. It returns a Markdown-friendly summary with the current
branch, clean or dirty state, tags, and recent commits. It does not expose
arbitrary shell execution.

```json
{"path": ".", "max_commits": 5}
```

### `write_text`

Writes UTF-8 text within the selected workspace. The step must declare
`"approval": "required"` and execution requires `--execute`, `--allow-writes`,
and `--approve <step-id>`.

```json
{"path": "outputs/brief.md", "content": "${{ steps.render.output }}"}
```

## Evidence

Each `run` creates `.workflow-runs/<run-id>/run.json`. The record contains:

- workflow name and run ID;
- mode and final status;
- step status;
- action metadata;
- file paths relative to the workspace;
- SHA-256 hashes and byte sizes;
- failure messages when a step is blocked or fails.

The record deliberately excludes file contents.
