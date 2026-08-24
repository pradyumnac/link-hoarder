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

## Metadata delivery review findings

The unpushed metadata changes have three unresolved findings:

- The import endpoint uses `queue_refresh_many` in `src/link_hoarder/api/app.py`. Large imports can use all visible-work capacity.
- `_submit` in `src/link_hoarder/core/metadata.py` does not prioritize visible refreshes. Executor order can keep visible work behind backfill work.
- `_refresh_with_generation` catches fetch errors only. Asset storage or metadata storage errors bypass failure caching and retry backoff.

## Task rail

No active session tasks.
