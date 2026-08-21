# Changelog

## [Unreleased]

### Added

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

- Build and publish complete Diataxis documentation (docs-diataxis-site).
- Add a versioned API contract, pagination, duplicate protection, and profile uploads (api-contract-v1).
- Apply Twelve-Factor runtime practices and document SQLite scaling exceptions (infra-twelve-factor).
- Add containers, tasks, official library skills, and release workflows (infra-stack-release, ADR-0001).
- Verify core, CLI, API, and packaging flows (test-release-gates, ADR-0001).

### Fixed

- Report browser import failures through the CLI, API, and web interface (import-warning-reporting).
- Harden API authentication, uploads, error responses, proxy limits, and browser headers (api-security-hardening).
