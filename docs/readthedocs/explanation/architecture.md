# Architecture

Link Hoarder separates behavior from delivery interfaces.
The core package owns models, storage, imports, settings, and logging.

The API uses the SQLite repository.
The CLI uses a typed backend interface with SQLite and HTTP implementations.
The import services use the same backend interface.
This design keeps command behavior consistent across backends.

The Vue browser interface calls the HTTP API through the frontend proxy.
Browser-local storage contains display settings only.
The server remains the source for bookmark data.

SQLite gives each Link Hoarder server one portable file.
SQLModel combines Pydantic validation with the object-relational mapping layer.

The API uses one configured key. This control fits a personal service behind a trusted network or reverse proxy.

The repository contains these developer records:

- [ADR-0001][adr-0001] records the application architecture.
- [ADR-0002][adr-0002] records CLI backend selection.
- The [Twelve-Factor audit][twelve-factor] records runtime exceptions.

[adr-0001]: https://github.com/pradyumnac/link-hoarder/blob/main/docs/adr/0001-application-architecture.md
[adr-0002]: https://github.com/pradyumnac/link-hoarder/blob/main/docs/adr/0002-cli-backend-selection.md
[twelve-factor]: https://github.com/pradyumnac/link-hoarder/blob/main/docs/developer/twelve-factor-audit.md
