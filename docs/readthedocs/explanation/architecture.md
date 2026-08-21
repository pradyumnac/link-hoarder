# Architecture

Link Hoarder separates behavior from delivery interfaces.
The core package owns models, storage, imports, settings, and logging.

The CLI and API call the same repository and importer functions. This design prevents behavior differences between interfaces.

SQLite gives the application one portable file.
SQLModel combines Pydantic validation with the object-relational mapping layer.

The API uses one configured key. This control fits a personal service behind a trusted network or reverse proxy.

See [ADR-0001](../../adr/0001-application-architecture.md) for the decision record.
