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
The file contains the backend, API URL, API key, and last successful export directory.
The setup task sets user-only permissions on this file.

The `export` command suggests the saved export directory in interactive mode.
An explicit directory can override the saved value.

## Environment variables

| Variable | Type | Default | Purpose |
| --- | --- | --- | --- |
| `LINK_HOARDER_BACKEND` | `local` or `api` | Saved value or `local` | Select the CLI backend. |
| `LINK_HOARDER_API_URL` | URL | Saved value | Set the API server root URL. Do not include `/api/v1`. |
| `LINK_HOARDER_API_KEY` | secret string | Saved value or none | Authenticate API clients and the API server. Use at least 32 characters. |
| `LINK_HOARDER_API_TIMEOUT_SECONDS` | number | `10` | Set the CLI HTTP timeout. Use a value greater than 0 and at most 120. |
| `LINK_HOARDER_DATABASE_PATH` | path | Platform user data directory | Select the local SQLite file. |
| `LINK_HOARDER_METADATA_CACHE_PATH` | path | Platform user data directory | Select the sanitized bookmark image directory. |
| `LINK_HOARDER_METADATA_REFRESH_ENABLED` | boolean | `true` | Enable background bookmark metadata refreshes. |
| `LINK_HOARDER_PREVIEW_PROVIDER` | `builtin` or `sidecar` | `builtin` | Select the link preview backend. |
| `LINK_HOARDER_PREVIEW_SERVICE_URL` | URL | `http://127.0.0.1:3001` | Set the preview sidecar base URL. |
| `LINK_HOARDER_LOG_LEVEL` | string | `INFO` | Set the structured log level. |
| `LINK_HOARDER_HOST` | string | `127.0.0.1` | Set the API bind host. |
| `LINK_HOARDER_PORT` | integer | `8000` | Set the direct API bind port. |

API mode requires an API URL and API key.
The direct API process also requires `LINK_HOARDER_API_KEY`.
The Docker stack generates and stores a key when the variable is not set.
In Docker Compose, `LINK_HOARDER_PORT` selects the frontend host port.
The Docker stack stores the metadata cache in its persistent data volume.
The Docker stack also runs the preview sidecar.
Set `LINK_HOARDER_PREVIEW_PROVIDER=sidecar` to use it.

## Browser settings

The web interface stores display settings in browser-local storage.
The storage key is `link-hoarder.browser-settings`.
These settings apply only to the current browser profile.

| Setting | Values | Default | Purpose |
| --- | --- | --- | --- |
| Page size | `10`, `25`, or `50` | `10` | Set the number of bookmarks on each page. |
| Default view | `list` or `gallery` | `list` | Select the initial collection view. |
| Accent color | Six-digit hexadecimal color | `#0d684d` | Set action, status, and unread-event accents. |

Use the color picker in Settings to select the accent color.
The web interface uses the defaults when the stored value is missing or invalid.

## UI variant session

The local Docker proxy stores the selected test variant in the `link_hoarder_variant` cookie.
The valid values are `stable` and `staging`. The cookie expires when the browser session ends.
The proxy uses `stable` when the cookie is missing or invalid.

The `version` query parameter selects a variant and replaces the session cookie value.
The proxy then redirects to the same path without the query string before it loads UI assets.
This setting applies only to the local Docker A/B test workflow.
