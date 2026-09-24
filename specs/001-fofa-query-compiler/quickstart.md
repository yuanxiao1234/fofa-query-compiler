# Quickstart Validation Guide

This guide defines the end-to-end evidence required after implementation. It does not deploy or submit
anything and does not require FOFA credentials. Run it from the repository root on Python 3.12+.

## 1. Install the local project

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Expected: the `fofa-compiler` command is available, tests can import the package, and no service is
started automatically.

## 2. Run deterministic tests

```bash
.venv/bin/python -m pytest
```

The suite must prove:

- Input schemas reject duplicate keys, duplicate/missing/unknown IDs, package mismatch, and invalid
  UTF-8 while accepting supported BOM input.
- Value properties cover IP/CIDR, ports `0/1/65535/65536`, ASN, timestamps, hashes, certificate serials,
  Unicode, quotes, backslashes, and regex.
- AST render/parse round trips preserve semantics and required Boolean grouping.
- Field-registry contracts reject unsupported field/operator/type combinations.
- CLI and Web application calls produce identical intent, validation, state, and export artifacts.
- CSRF, loopback binding, revision conflicts, path containment, and export gates cannot be bypassed.
- Fake or recorded model adapters are used; default tests do not call a network.

## 3. Import the current 100-question package

```bash
fofa-compiler import \
  --questions 题目/题目.md \
  --package 题目/参赛包.md \
  --template 题目/答案模板.md \
  --workspace .local/pkg-08e82c8d
```

Expected:

- Package ID is `pkg-08e82c8d`.
- Exactly 100 unique question IDs are imported.
- Question and template ID sets are equal.
- Original question order and all three source digests are recorded.
- Original files remain unchanged.

Repeat with fixtures containing one missing ID, one duplicate, one unknown ID, an invalid package ID,
and malformed JSON. Each import must fail with a precise diagnostic and no partial run.

## 4. Generate and validate candidates

```bash
fofa-compiler generate --workspace .local/pkg-08e82c8d --offline
fofa-compiler validate --workspace .local/pkg-08e82c8d
fofa-compiler status --workspace .local/pkg-08e82c8d --json
```

Expected:

- Every question has a candidate, deterministic rejection, or explicit blocking/failure state.
- One failed question does not hide successful results for the other questions.
- Invalid port/IP, contradiction, subjective criteria, and unavailable runtime telemetry fixtures use
  the exact rejection text.
- External-source access failure is `evidence_blocked`, never automatic rejection.
- Status does not claim export readiness because human confirmation is incomplete.

## 5. Validate the local Web UI

```bash
fofa-compiler web --workspace .local/pkg-08e82c8d --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765` and verify:

1. The overview shows the same totals as CLI status.
2. Starting a generation job shows sequenced progress no later than every two seconds.
3. Refreshing the page restores current job and saved question states.
4. Filters locate evidence-blocked, validation-failed, high-risk, and unconfirmed questions.
5. A question detail shows source text, constraints, candidate, validation, risks, and evidence.
6. Editing a candidate creates a revision, reruns validation, and invalidates prior confirmation.
7. A stale second tab receives a revision conflict instead of overwriting the newer edit.
8. A high-risk item cannot be confirmed until its risk and evidence checklist is complete.
9. The export page lists all blockers and provides no force-export path.
10. Non-loopback binding and write requests without CSRF protection are rejected.

## 6. Complete evidence and review

For every external-source item, add the primary source or a qualified official alternative, verified
archive, or user-provided verifiable material. Record extracted facts, content digest, access status,
and reviewer verification. An unavailable primary may remain in history but cannot itself satisfy the
evidence requirement.

Review all 100 items individually in the Web UI or CLI. For each item:

- Check every atomic constraint against the candidate.
- Confirm the current passing validation report.
- For high-risk items, complete every risk check and required evidence link.
- If edited, revalidate and reconfirm the new revision.

Expected final status: 100/100 confirmed, no validation failures, no evidence blocks, no stale reviews,
and all high-risk checks complete.

## 7. Export through CLI and Web

```bash
fofa-compiler export \
  --workspace .local/pkg-08e82c8d \
  --participant '实际选手名称' \
  --output .local/答案-cli.json
```

Then export the same run from the Web export page as `.local/答案-web.json`.

Validate both artifacts:

```bash
.venv/bin/python -m json.tool .local/答案-cli.json >/dev/null
.venv/bin/python -m json.tool .local/答案-web.json >/dev/null
cmp .local/答案-cli.json .local/答案-web.json
```

Expected:

- Both files parse as JSON and are equivalent byte-for-byte under the canonical export policy.
- Package ID is exact, answer count is 100, IDs are unique and in original order, and every query is
  non-empty.
- No candidate, explanation, Markdown, AST, evidence, audit, secret, or internal state is present.
- Each file is below 8 MB and its displayed SHA-256 matches the downloaded content.

## 8. Prove negative export gates

Using isolated fixture workspaces, attempt export with each condition below:

- one missing answer;
- one duplicate or unknown ID;
- one validation failure;
- one unconfirmed ordinary item;
- one high-risk item with an unchecked risk;
- one evidence-blocked item;
- one edit whose old confirmation is stale;
- a non-exact rejection string;
- an output exceeding the size limit.

Every attempt must fail, list all blockers, and neither create a partial target nor overwrite an existing
valid export.

## 9. Accuracy and reproducibility acceptance

Two independent reviewers judge each benchmark fixture against field, match mode, value, logic,
negation, and boundary constraints. Any failed applicable constraint fails the whole item; disagreements
require adjudication. Convertible items must reach at least 95% whole-item accuracy, and defined
non-convertible cases must reach 100% rejection accuracy.

With input, rule, registry, adapter response, evidence, and confirmation fingerprints frozen, run the
pipeline and export three times. Normalized answers and exported bytes must be identical in all runs.
