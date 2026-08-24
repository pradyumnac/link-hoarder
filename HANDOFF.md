# Handoff

Store unresolved session findings in this file. Move each finding to its permanent record when possible.

## Execution state

`main` contains the accepted compact-header redesign.
The worktree is clean after the accepted change.

The local ignored `stack/.env` sets `LINK_HOARDER_AB_ENABLED=true`.
The A/B stack runs at `http://127.0.0.1:8080`.
The root page and health endpoint return HTTP 200.
Stable and Staging use the accepted UI.
The A/B proxy sets the variant cookie and redirects before UI assets load.
`mise run ab-check` passes for Stable and Staging.

## Branch and A/B workflow

Use one short-lived branch for each numbered redesign task. Create each branch from the accepted `main` baseline.
Use a `ui/` branch name and make only the selected task change.

Run `mise run ab-stage` to build the active branch as Staging.
Use the top-bar Test UI control to compare Stable and Staging.
Run `mise run ab-reset` after a rejected change.
After an accepted branch reaches `main`, run `mise run ab-promote`.

Stable and Staging share one API and bookmark database.
Do not use data mutations as evidence of a UI difference.
Follow `docs/readthedocs/how-to/ab-switching.md` for operator instructions.
Run `mise run check` before each branch is complete.

## Deferred UI redesign sequence

After the compact header, continue with these changes:

1. Restructure the collection navigation.
2. Replace mobile folder navigation.
3. Simplify folder navigation.
4. Add active-filter chips.
5. Persist collection state in the URL.
6. Add sorting and a results toolbar.
7. Redesign bookmark rows.
8. Move secondary actions into an overflow menu.
9. Evaluate the gallery view.
10. Add contextual empty and loading states.
11. Move collection queries to the API.
12. Improve folder and tag entry.
13. Improve form validation and submission.
14. Redesign import.
15. Correct modal accessibility.
16. Correct popup and combobox accessibility.
17. Audit visual and touch accessibility.
18. Validate each redesign with A/B checks.

## Task rail

No active session tasks.
