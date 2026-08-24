# Handoff

Store unresolved session findings in this file. Move each finding to its permanent record when possible.

## Execution state

`main` contains the opt-in A/B infrastructure and is synchronized with `origin/main`.
The A/B implementation baseline is commit `96b84a0`. Commit `33b7a38` advances this task rail.
The worktree was clean before this handoff update.

The local ignored `stack/.env` sets `LINK_HOARDER_AB_ENABLED=true`.
The A/B stack runs at `http://127.0.0.1:8080`.
The API and proxy are healthy. Stable and Staging use image `sha256:830bec401121b1ced11210b8068f3732ccaaa029a2b00b0d6850a107886ba41f`.
Both variants currently show the same UI.

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

## Next task acceptance criteria

Task 2 replaces the large hero with a compact application header and makes search the primary control.
Start a new branch from `main`, such as `ui/compact-header-search`.

Keep these controls in the header:

- Link Hoarder brand.
- Global bookmark search.
- Add bookmark.
- Import bookmarks.
- Test UI selector when A/B mode is enabled.
- Settings.
- Notifications.

Add a clear-search control when the query is not empty.
Make `/` focus search unless focus is in an editable control.
Keep the existing 300 ms search delay.
Remove the redundant Search submit icon after automated and manual validation.
Keep all controls usable at 320 px and without overlap at desktop widths.
Give each icon an accessible name and a visible focus state.

Before implementation, add primary, alternate, edge, and negative flows to `docs/developer/test-plan.md`.
Add BDD-style unit tests for clear search, slash focus, editable-control exclusion, and responsive control presence.
Deploy only Staging during evaluation. Do not promote the change without user approval.

## Task rail

| Rail ID | Task | Scope | Status |
| --- | --- | --- | --- |
| 1 | Establish the A/B baseline. | Keep Stable and Staging on the accepted `main` UI. | done |
| 2 | Add a compact header and primary search. | Keep core actions in the header. Add clear search and `/` focus. Remove the submit icon after validation. | active |
| 3 | Restructure collection information architecture. | Organize navigation around All bookmarks, Folders, Tags, Bookmarklets, and Recent. | pending |
| 4 | Replace mobile folder navigation. | Use a drawer or bottom sheet. Show search, filter count, active filters, and results first. | pending |
| 5 | Simplify folder navigation. | Use an expandable desktop tree, searchable mobile picker, conditional breadcrumbs, and folder counts. | pending |
| 6 | Add active-filter chips. | Show folder, tag, and type chips. Add independent removal, filtered count, and Clear all. | pending |
| 7 | Persist collection state in the URL. | Persist search, filters, folder, sort, view, and page. Support refresh and browser history. | pending |
| 8 | Add sorting and a results toolbar. | Support title, added date, updated date, and domain sorting. Consolidate result controls. | pending |
| 9 | Redesign bookmark rows. | Link the title. Show a short domain, favicon, folder, tags, and useful date metadata. | pending |
| 10 | Move secondary actions into an overflow menu. | Reduce repeated icons and replace native delete confirmation with an application dialog. | pending |
| 11 | Evaluate gallery view. | Add useful gallery metadata or replace gallery with compact and comfortable list densities. | pending |
| 12 | Add contextual empty and loading states. | Distinguish empty collection, empty search, and empty filters. Add skeletons and recovery actions. | pending |
| 13 | Move collection queries to the API. | Add server-side filtering, sorting, pagination, and filter metadata. Stop loading all matches. | pending |
| 14 | Improve folder and tag entry. | Suggest existing values. Replace comma-separated tags with tag chips. | pending |
| 15 | Improve form validation and submission. | Add inline errors, pending state, failed-input preservation, and unsaved-change warnings. | pending |
| 16 | Redesign import. | Add guidance, drag-and-drop, progress, result counts, and warning review. | pending |
| 17 | Correct modal accessibility. | Trap focus, make the background inert, support Escape, and restore focus. | pending |
| 18 | Correct popup and combobox accessibility. | Add outside-click, Escape, mutual exclusion, and complete combobox keyboard behavior. | pending |
| 19 | Audit visual and touch accessibility. | Add tooltips, 44 px targets, focus indicators, contrast, zoom, and reduced-motion support. | pending |
| 20 | Validate each redesign with A/B checks. | Test desktop and mobile find, open, save, organize, import, and recovery tasks before promotion. | pending |
