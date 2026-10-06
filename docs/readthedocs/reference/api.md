# HTTP API reference

Send `X-API-Key` with every request. The key must contain at least 32 characters.
The repository contains the [OpenAPI contract](https://github.com/pradyumnac/link-hoarder/blob/main/docs/openapi.json).
Runtime documentation routes are disabled.

Resource routes use the `/api/v1` prefix. The `/health` route is not versioned.

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/health` | Return server health. |
| `POST` | `/api/v1/bookmarks` | Create a bookmark. |
| `GET` | `/api/v1/bookmarks` | List or search bookmarks. |
| `GET` | `/api/v1/bookmarks/{id}` | Get one bookmark. |
| `PATCH` | `/api/v1/bookmarks/{id}` | Update supplied fields. |
| `DELETE` | `/api/v1/bookmarks/{id}` | Delete one bookmark. |
| `POST` | `/api/v1/imports/bookmarks-file` | Import a bookmark HTML export. |
| `POST` | `/api/v1/imports/bookmarks-json` | Import a bookmark JSON export. |

The list response contains `items`, `total`, `limit`, and `offset` fields.
The list accepts `query`, `limit`, `offset`, and `sort` parameters.
The `sort` parameter accepts `newest` or `oldest` and orders by original save
time. Imports preserve the save time from the source profile or export.
Create and update operations return HTTP 409 when a normalized URL already exists.
Imports skip an existing normalized URL and increment the `skipped` count.
The HTML import response includes structured warnings for invalid entries, unreadable
exports, malformed files, and storage failures. Valid entries continue to import.
The JSON import accepts a JSON array of bookmarks and rejects invalid entries
with HTTP 422. The maximum JSON import size is 50000 bookmarks.

Send a Netscape bookmark export as `text/html`. The maximum file size is 16 MiB.
Send a CLI JSON export as `application/json`.
The web API does not accept native browser profiles or server-local paths.
