# Handoff

Store unresolved session findings in this file. Move each finding to its permanent record when possible.

## Execution state

`main` contains the accepted compact-header, collection-navigation, and wide-layout redesigns.
The active branch contains ADR 0005 with every blocking metadata delivery fix applied, the
background metadata sweeper, and the collection layout correction. Nothing is pushed.

The local ignored `stack/.env` sets `LINK_HOARDER_AB_ENABLED=true`.
The A/B stack runs at `http://127.0.0.1:8080`. The root page and health endpoint return HTTP 200.
`mise run ab-check` reports that Stable and Staging now DIFFER: Staging carries the new
collection layout, Stable does not. Promote with `mise run ab-promote` after visual review.

`link-hoarder-api:before` is the pre-session API image, kept for comparison. Restore it with
`docker tag link-hoarder-api:before link-hoarder-api:local` and recreate the `api` service.

The A/B split is frontend only. `stack/compose.ab.yaml` defines one shared `api` service, so a
backend change cannot be staged as a variant and reaches both variants at once.

## Metadata status is not link health

`BookmarkMetadataRecord.status` holds `READY`, `FAILED`, or `BLOCKED`. This records the result of
one metadata fetch. It is not a reachability signal, and it must not be presented as one.

Live data shows why. `BLOCKED` currently covers `fahdmirza.com`, `notebooklm.google.com`,
`gemini.google.com`, and `youtube.com` playlists, which are all reachable. They tripped this
application's own page-size or redirect limits. Only `192.168.128.101:8006` is a true policy
block. `FAILED` mixes a permanent DNS failure with a transient network error in the same value.

The record also stores no reason, only the enum, so the two cases cannot be separated today.
`core-metadata-reason` covers adding that reason and needs a schema migration.

The status is not exposed in any API response and is not a bookmark tag. Real reachability
tracking belongs to `core-health-policy` and `core-link-health`, and surfacing the fetch outcome
belongs to `core-metadata-diagnostics`.

## Next parallel run plan

Plan only. Nothing here is launched yet. The run that owned
`core/metadata.py`, `core/repository.py`, and `frontend/src/App.vue` has
merged, so wave 1 is ready to launch.

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
available, so this table is the only record.

| ID | Status | Task | Blocked by |
| --- | --- | --- | --- |
| core-metadata-svg.icons | blocked | Rasterize SVG site icons to PNG before rejecting them. ADR 0005 decided not to accept remote SVG, so the decision must change first. A rasterizer is also a new dependency, and `cairosvg` needs native cairo on Windows. | ADR 0005 amendment, dependency review |
| core-metadata-reason | pending | Store why a metadata fetch was blocked or failed. Today only the status enum is kept, so a policy block cannot be told apart from a tripped size or redirect limit. | infra-schema-migrations |
| test-metadata-delivery | pending | Validate metadata delivery with malformed URLs and 1,500 bookmarks. | |
