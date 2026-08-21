# Twelve-Factor App audit

This audit records how Link Hoarder applies the Twelve-Factor App method.
ADR-0001 requires SQLite, so the audit records SQLite limits as explicit exceptions.

| Factor | Status | Implementation or exception |
| --- | --- | --- |
| Codebase | Compliant | Git contains one codebase for the CLI, API, and web interface. |
| Dependencies | Compliant | `uv.lock` and `frontend/package-lock.json` lock declared dependencies. Containers install from these locks. |
| Configuration | Partial | Runtime settings read environment variables only. Docker Compose passes `stack/.env` values as environment variables. The generated API key persists in a secret volume. The CLI config file stores user backend and export preferences. |
| Backing services | Partial | The database path is configurable. ADR-0001 requires SQLite, so the app cannot replace SQLite with a remote database through configuration. |
| Build, release, run | Compliant | Python, frontend, and container builds are separate from runtime commands. The release workflow builds from a version tag. |
| Processes | Compliant with exception | Runtime processes keep temporary state only. SQLite data and the generated secret use named volumes. CLI export writes user-requested durable files outside the process. Browser display preferences use browser-local storage. |
| Port binding | Compliant | Uvicorn and nginx export services through configured ports. Compose publishes only nginx. |
| Concurrency | Partial | The web proxy can scale independently. SQLite write locking limits horizontal API scaling. |
| Disposability | Compliant | Entrypoints use `exec`, Compose uses an init process, and shutdown closes the database engine. Native Firefox-family import uses a read-only SQLite snapshot. |
| Development parity | Compliant | Local and container builds use the same lockfiles, SQLite backend, and generated OpenAPI contract. |
| Logs | Compliant | API events use structured JSON on standard output. CLI diagnostics, warnings, and debug checkpoints use standard error. Command results use standard output. |
| Admin processes | Compliant | CLI import, export, and CRUD commands use the same code and dependency set as the application. Mise tasks use the locked environment. |

## Required operating rules

- Pass application configuration through environment variables.
- Keep SQLite data on a persistent volume in containers.
- Keep the API process behind the frontend proxy for remote use.
- Build release artifacts once. Run the same artifacts in each environment.
- Send process logs to standard output or standard error.
- Keep command results on standard output and CLI diagnostics on standard error.
- Treat saved CLI paths as user preferences, not runtime deployment configuration.
- Read live browser databases through read-only snapshots.
