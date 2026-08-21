# Changelog

## [Unreleased]

### Added

- Support JavaScript bookmarklets in the CLI, API, and browser imports (core-bookmarklet-support).
- Automatically tag JavaScript bookmarklets and search bookmark tags (core-bookmarklet-tags).
- Add a Vue web interface with an auto-provisioned Docker stack (infra-web-interface).
- Add typed SQLite bookmark CRUD (core-storage-crud, ADR-0001).
- Import native Chromium and Firefox profiles (import-profile-native, ADR-0001).
- Expose CRUD and imports through Typer (cli-command-surface, ADR-0001).
- Expose authenticated CRUD and imports through FastAPI (api-command-surface, ADR-0001).

### Changed

- Add a versioned API contract, pagination, duplicate protection, and profile uploads (api-contract-v1).
- Add containers, tasks, official library skills, and release workflows (infra-stack-release, ADR-0001).
- Verify core, CLI, API, and packaging flows (test-release-gates, ADR-0001).

### Fixed
