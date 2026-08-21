# Configuration reference

Link Hoarder reads environment variables with the `LINK_HOARDER_` prefix.

| Variable | Type | Default | Purpose |
| --- | --- | --- | --- |
| `LINK_HOARDER_DATABASE_PATH` | path | Platform user data directory | Select the SQLite file. |
| `LINK_HOARDER_API_KEY` | secret string | None | Authorize API requests with `X-API-Key`. |
| `LINK_HOARDER_LOG_LEVEL` | string | `INFO` | Set the structured log level. |
| `LINK_HOARDER_HOST` | string | `127.0.0.1` | Set the API bind host. |
| `LINK_HOARDER_PORT` | integer | `8000` | Set the API bind port. |

The API does not start without `LINK_HOARDER_API_KEY`.
