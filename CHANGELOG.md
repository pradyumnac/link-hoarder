# Changelog

## [Unreleased]

### Added

- Make search the primary control in a compact, themeable application header (ui-header-compact).
- Export bookmarks to browser-compatible HTML and structured JSON files (cli-bookmark-export).
- Import native Brave and Zen browser profiles (import-brave.zen-native).
- Add responsive browser views, filters, folder navigation, saved display settings, and modal workflows (core-browser-workspace).
- Add a browser notification center for session failure events (core-failure-notifications).
- Show import summaries and duplicate skips as notification events (core-import-events).
- Add interchangeable local and API CLI backends with interactive user setup (cli-backend-selection, ADR-0002).
- Support JavaScript bookmarklets in the CLI, API, and browser imports (core-bookmarklet-support).
- Automatically tag JavaScript bookmarklets and search bookmark tags (core-bookmarklet-tags).
- Add a Vue web interface with an auto-provisioned Docker stack (infra-web-interface).
- Import Netscape bookmark HTML exports through the CLI and web interface (import-html-export).
- Add typed SQLite bookmark CRUD (core-storage-crud, ADR-0001).
- Import native Chromium and Firefox profiles (import-profile-native, ADR-0001).
- Expose CRUD and imports through Typer (cli-command-surface, ADR-0001).
- Expose authenticated CRUD and imports through FastAPI (api-command-surface, ADR-0001).

### Changed

- Bound the metadata refresh queue and reserve capacity for visible bookmarks (core-metadata-scheduling, ADR-0005).

- Add secure cached bookmark icons, concise links, and gallery thumbnails (core-bookmark-presentation, ADR-0005).
- Scale collection navigation, gallery columns, and workspace width across desktop and 4K screens (core-wide-layout).
- Restructure collection navigation with smart destinations, source filters, and a responsive drawer (core-navigation-restructure).
- Make CLI output readable, debuggable, repeatable, and explicit about error states (cli-output-resilience).
- Read live Firefox and Zen databases through stable, read-only SQLite snapshots (import-live-snapshot).
- Build and publish complete Diataxis documentation (docs-diataxis-site).
- Add a versioned API contract, pagination, duplicate protection, and profile uploads (api-contract-v1).
- Apply Twelve-Factor runtime practices and document SQLite scaling exceptions (infra-twelve-factor).
- Add containers, tasks, official library skills, and release workflows (infra-stack-release, ADR-0001).
- Verify core, CLI, API, and packaging flows (test-release-gates, ADR-0001).

### Fixed

- Add cache headers and ETags to bookmark asset routes (api-asset-caching, ADR-0005).
- Read bookmark presentation metadata for one page in one query (api-metadata-query-load, ADR-0005).
- Queue metadata for exactly the bookmarks an import creates, at every library size (import-metadata-refresh, ADR-0005).
- Normalize destination errors and back off repeated metadata failures (core-metadata-failure-cache, ADR-0005).
- Cancel metadata work for deleted bookmarks without suppressing reused row identifiers (core-metadata-retirement, ADR-0005).

- Report browser import failures through the CLI, API, and web interface (import-warning-reporting).
- Harden API authentication, uploads, error responses, proxy limits, and browser headers (api-security-hardening).
