# HTTP API reference

Send `X-API-Key` with every request. Open `/docs` for the generated OpenAPI interface.
The committed contract is in [`docs/openapi.json`](../../openapi.json).

Resource routes use the `/api/v1` prefix. The `/health` route is not versioned.

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/health` | Return server health. |
| `POST` | `/api/v1/bookmarks` | Create a bookmark. |
| `GET` | `/api/v1/bookmarks` | List or search bookmarks. |
| `GET` | `/api/v1/bookmarks/{id}` | Get one bookmark. |
| `PATCH` | `/api/v1/bookmarks/{id}` | Update supplied fields. |
| `DELETE` | `/api/v1/bookmarks/{id}` | Delete one bookmark. |
| `POST` | `/api/v1/imports/browser` | Import a server-local browser profile. |
| `POST` | `/api/v1/imports/browser-file` | Import an uploaded browser profile. |

The list response contains `items`, `total`, `limit`, and `offset` fields.
Create and update operations return HTTP 409 when a normalized URL already exists.
Browser imports skip an existing normalized URL and increment the `skipped` count.
The import response includes structured warnings for invalid entries, unreadable
profiles, malformed files, and storage failures. Valid entries continue to import.

Send uploaded profile bytes as `application/octet-stream`. Set the `browser` query
parameter to `chrome`, `chromium`, `edge`, or `firefox`.
