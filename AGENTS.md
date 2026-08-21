# Agent instructions

Read `.methodology.toml` and `CONTEXT.md` before you change project behavior.

## Documentation boundaries

| Path | Content |
| --- | --- |
| `AGENTS.md` | Agent behavior and workflow |
| `CONTEXT.md` | Scope, architecture, and glossary |
| `README.md` | Public installation and use |
| `docs/readthedocs/` | Diataxis user documentation |
| `docs/adr/` | Architecture decision records |

Keep each fact in one source file. Link to that source from other documents.

## Project rules

- Support Python 3.14 on Windows and Linux.
- Use `uv` for Python packages.
- Use mise tasks for each development command.
- Keep all public and internal code strictly typed.
- Do not use explicit `Any` types.
- Validate values at module boundaries with Pydantic models.
- Emit structured logs with structlog.
- Follow trunk-based development on `main`.
- Write Conventional Commit messages.
- Do not add AI or tool attribution to commits.

## Task tracking

Managed by the `todo-md-lite` skill.

- todo_file: TODO.md
- prefixes: core, cli, api, import, infra, docs, test
- done_handling: changelog
- changelog_file: CHANGELOG.md
- lint_tables_exempt: true
- lint_line_limit: 120

## Decision records

Managed by the `adr-lifecycle` skill.

- adr_dir: docs/adr
- index_file: docs/adr/INDEX.md

Create an ADR only when a decision is significant, hard to reverse, and not recorded elsewhere.

## Handoff notes

Managed by the `handoff` skill.

- handoff_file: HANDOFF.md

## Tests

- Write a test plan before you add tests.
- Test primary, alternate, edge, and negative flows.
- Add integration tests for multi-step workflows.
- Add a BDD-style docstring to each unit test.
- Run `mise run check` before you finish a change.

## Documentation

- Apply ASD-STE100 Simplified Technical English.
- Use Diataxis for user documentation.
- Put Diataxis pages under `docs/readthedocs/`.
- Put developer-only context in the applicable root or developer path.
- Document configuration in `docs/readthedocs/reference/configuration.md`.
