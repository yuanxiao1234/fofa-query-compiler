# CLI Contract

## Entry Point

```text
fofa-compiler import   --questions PATH --package PATH --template PATH --workspace DIR
fofa-compiler generate --workspace DIR [--question-id ID] [--offline]
fofa-compiler validate --workspace DIR [--question-id ID]
fofa-compiler review   --workspace DIR --question-id ID
fofa-compiler evidence add --workspace DIR --question-id ID --source VALUE --kind KIND
fofa-compiler status   --workspace DIR [--json]
fofa-compiler export   --workspace DIR --participant NAME --output PATH
fofa-compiler web      --workspace DIR [--host 127.0.0.1] [--port 8765] [--no-open]
```

The Web command rejects non-loopback hosts in v1. All commands call application services also used by
the Web UI. No command may directly mutate the submitted answer template.

## Behavioral Contract

- Human-readable output goes to stdout; diagnostics go to stderr.
- `status --json` emits a stable object containing package ID, total, converted, refused, validation
  failures, review-required, confirmed, evidence-blocked, export-ready, and all blockers.
- Batch commands preserve successful item results when another item fails, then report aggregate status.
- Writes validate completely before atomic replacement; a failed operation leaves the prior state intact.
- `review` shows original text, normalized intent, constraints, AST/query or rejection, validation,
  risks, evidence, and revision. Editing creates a new revision and clears prior confirmation.
- Confirmation requires an explicit human action for every question. There is no bulk-confirm command.
- `export` has no force option and never produces a partial answer sheet.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Command completed; status may still report pending work |
| 2 | Invalid arguments, path, or usage |
| 3 | Input parsing or schema validation failed |
| 4 | Package integrity failed: IDs, count, duplicates, or package mismatch |
| 5 | Generation dependency unavailable or candidate generation failed |
| 6 | Query/IR deterministic validation failed |
| 7 | Evidence missing, unqualified, or blocked |
| 8 | Human confirmation or high-risk checks incomplete |
| 9 | Export preflight failed |
| 10 | Output write failed; prior target remains intact |
| 11 | Workspace schema/version invalid or corrupted |
| 70 | Unclassified internal error |

For a batch with multiple error classes, the command returns the most severe applicable non-zero code
and prints all item findings rather than stopping at the first question.

## Input Compatibility

The primary package contract is the competition JSON/TXT format. The current repository's `.md` files
are accepted only through an explicit content adapter because they contain JSON or plain text. UTF-8 and
UTF-8 BOM are accepted. Duplicate JSON keys, duplicate IDs, empty required values, and silent extension-
based guessing are rejected.
