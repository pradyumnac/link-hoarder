# HTTP API reference

Send `X-API-Key` with every request. Open `/docs` for the generated OpenAPI interface.

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/health` | Return server health. |
| `POST` | `/bookmarks` | Create a bookmark. |
| `GET` | `/bookmarks` | List or search bookmarks. |
| `GET` | `/bookmarks/{id}` | Get one bookmark. |
| `PATCH` | `/bookmarks/{id}` | Update supplied fields. |
| `DELETE` | `/bookmarks/{id}` | Delete one bookmark. |
| `POST` | `/imports/browser` | Import a native browser profile. |
