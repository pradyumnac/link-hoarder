# Handoff

Store unresolved session findings in this file. Move each finding to its permanent record when possible.

## Execution state

`main` contains the accepted compact-header, collection-navigation, and wide-layout redesigns.
The active branch contains ADR 0005 implementation with every blocking metadata delivery fix applied.
`test-metadata-delivery` is the one remaining row for ADR 0005.

The local ignored `stack/.env` sets `LINK_HOARDER_AB_ENABLED=true`.
The A/B stack runs at `http://127.0.0.1:8080`.
The root page and health endpoint return HTTP 200.
Stable and Staging use the accepted UI.
The A/B proxy sets the variant cookie and redirects before UI assets load.
`mise run ab-check` passes for Stable and Staging.

## Next parallel run plan

Plan only. Nothing here is launched yet. The current run owns
`core/metadata.py`, `core/repository.py`, `api/app.py`, and
`frontend/src/App.vue`, so every wave below starts after that run merges.

Agent count is set by file ownership, not by task count. Two agents must
never own one file. `frontend/src/App.vue` is a single 1040-line file, so
every frontend row in a wave goes to one agent.

Each row below was verified against the code, not taken from the row text.

### Wave 1 — four agents, disjoint files

| Agent | Owns | Rows |
| --- | --- | --- |
| N1 | `core/metadata.py`, `tests/test_metadata.py` | core-metadata-charset, core-metadata-cache.cleanup, api-metadata-shutdown (service side) |
| N2 | `api/app.py`, `core/repository.py`, `tests/test_api.py` | api-delete-atomicity, api-metadata-shutdown (lifespan side) |
| N3 | `frontend/src/App.vue`, `frontend/src/style.css`, `frontend/tests/` | core-view-density, core-actions-overflow, core-navigation-disclosure, core-thumbnail-recovery, infra-ab-controls |
| N4 | `docs/adr/` | Draft proposals for core-bookmark-lifecycle, core-domain-taxonomy, core-health-policy, core-visit-policy |

Fixed seam between N1 and N2, to agree before launch: `close()` blocks the
event loop because it calls `ThreadPoolExecutor.shutdown(wait=True)` from
async lifespan code. N1 adds `async def aclose()` to
`BookmarkMetadataService`. N2 awaits it in the lifespan. Land the method
signature on the branch first, as was done for `list_metadata`, or N2
cannot type-check.

N4 drafts decision records only. It proposes options and trade-offs and
does not accept any decision. Each of the four design rows needs a human
choice, and those choices block seven later rows.

### Wave 2 — one agent, then two

`infra-schema-migrations` runs alone. It rewrites `initialize()` and adds a
migration module, it has the largest blast radius of any open row, and it
unblocks seven rows. It must not share `core/repository.py` with anything.

After it merges:

| Agent | Owns | Rows |
| --- | --- | --- |
| N5 | `core/repository.py`, `api/app.py`, `frontend/src/App.vue` | api-collection-query |
| N6 | `core/metadata.py`, `api/app.py`, `frontend/src/App.vue` | core-metadata-diagnostics |

N5 and N6 both need `api/app.py` and `App.vue`, so they cannot run
together. Run N5 first: `core-filter-chips`, `core-results-sorting`, and
`core-result-grouping` all depend on it, and none depend on N6.

### Wave 3 — wide parallelism

`infra-schema-migrations` unblocks `core-tag-taxonomy`,
`core-content-formats`, `api-search-index`, and, once the wave 1 design
rows are decided, `core-lifecycle-storage`, `core-domain-storage`,
`core-link-health`, and `core-visit-tracking`. Each adds its own table and
its own module, so these split cleanly. Re-check ownership before launch.

### Rows deliberately not scheduled

`core-metadata-svg.icons` stays blocked. It needs an ADR 0005 amendment and
a dependency review, and the obvious rasterizer needs native cairo on
Windows, which conflicts with the Windows and Linux support rule.

## Task rail

Mirrors the `Todo` section of `TODO.md`. The session task rail tool was not
available when this was written, so this table is the only record.

| ID | Status | Task | Blocked by |
| --- | --- | --- | --- |
| core-metadata-promotion | pending | `_pending` does not record the queue kind, so a visible request for a bookmark already queued for backfill returns early instead of promoting it. See `_submit` in `src/link_hoarder/core/metadata.py`. | |
| core-metadata-failure.memory | pending | When the metadata write and the failure-record write both fail, no backoff state remains and each collection request refetches the remote URL. See `_refresh_with_generation` and `_record_failure`. | |
| core-metadata-backfill.sweep | pending | Backfill runs only on import. 846 of 1501 bookmarks have no metadata row and nothing sweeps them. Needs an idempotent bulk sweep that triggers when data is missing. | |
| core-metadata-svg.icons | blocked | Rasterize SVG site icons to PNG before rejecting them. ADR 0005 decided not to accept remote SVG, so the decision must change first. A rasterizer is also a new dependency, and `cairosvg` needs native cairo on Windows. | ADR 0005 amendment, dependency review |
| api-availability-favicon | pending | `BookmarkAssetAvailability.has_favicon` costs two disk stats for each bookmark on each page, and `_present_bookmark` never reads it. | |
| core-collection-presentation | pending | Collection list and gallery layout: unused horizontal space, ragged gallery card heights, URLs that break mid-word, and weak row hierarchy. | |
| test-metadata-delivery | pending | Validate metadata delivery with malformed URLs and 1,500 bookmarks. | core-metadata-promotion, core-metadata-failure.memory, core-metadata-backfill.sweep, api-availability-favicon |
