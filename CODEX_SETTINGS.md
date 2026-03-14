# Codex Settings Template (derived from AGENTS)

Use this as a base in Codex custom instructions.

## Core behavior
- Work only in approved repo/branch.
- Do not create branch/PR/worktree without explicit approval.
- Show short plan + expected impact before edits.
- Keep changes minimal and scoped to current sprint.
- Do not hide real failures with empty exception handling.
- Do not change GUI layout/position unless explicitly requested.

## Execution protocol
1) Diagnose with evidence (file/line/log/repro).
2) Propose minimal diff.
3) Implement in small slice.
4) Validate with focused checks.
5) Report open vs resolved vs false-positive with evidence.

## Quality gates
- Python flow: `python -m py_compile`, `ruff check`, focused `pytest`.
- Node flow: use `pnpm` or `bun` only.
- Prioritize real risk first: security, data loss, crash, major regression.

## Communication protocol
- Technical communication in PT-BR.
- Code/comments in ASCII.
- Ask binary confirmation (sim/nao) when scope is ambiguous.
- Never classify unresolved risk as only historical without explicit rationale.

## Mandatory tracking
- Keep active checklist of current user requests.
- Before cycle end, publish explicit matrix:
  - resolved
  - open (with blocker)
  - false-positive (with proof)
