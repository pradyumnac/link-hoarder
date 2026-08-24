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
