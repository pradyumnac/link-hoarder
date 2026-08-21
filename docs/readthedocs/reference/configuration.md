# Configuration reference

Link Hoarder reads environment variables with the `LINK_HOARDER_` prefix.
The application does not read `.env` files. Docker Compose reads `stack/.env` and passes its values through the environment.

## Configuration precedence

The CLI selects its backend in this order:

1. The global `--backend` option.
2. Environment variables.
3. The saved user configuration.
4. The local SQLite backend.

The setup task writes `config.json` in the platform configuration directory.
On Linux, the default path is `~/.config/link-hoarder/config.json`.
The file contains the backend, API URL, and API key.
The setup task sets user-only permissions on this file.

## Environment variables

| Variable | Type | Default | Purpose |
| --- | --- | --- | --- |
| `LINK_HOARDER_BACKEND` | `local` or `api` | Saved value or `local` | Select the CLI backend. |
| `LINK_HOARDER_API_URL` | URL | Saved value | Set the API server root URL. Do not include `/api/v1`. |
| `LINK_HOARDER_API_KEY` | secret string | Saved value or none | Authenticate API clients and the API server. Use at least 32 characters. |
| `LINK_HOARDER_API_TIMEOUT_SECONDS` | number | `10` | Set the CLI HTTP timeout. Use a value greater than 0 and at most 120. |
| `LINK_HOARDER_DATABASE_PATH` | path | Platform user data directory | Select the local SQLite file. |
| `LINK_HOARDER_LOG_LEVEL` | string | `INFO` | Set the structured log level. |
| `LINK_HOARDER_HOST` | string | `127.0.0.1` | Set the API bind host. |
| `LINK_HOARDER_PORT` | integer | `8000` | Set the direct API bind port. |

API mode requires an API URL and API key.
The direct API process also requires `LINK_HOARDER_API_KEY`.
The Docker stack generates and stores a key when the variable is not set.
In Docker Compose, `LINK_HOARDER_PORT` selects the frontend host port.
