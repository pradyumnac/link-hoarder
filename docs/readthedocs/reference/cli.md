# CLI reference

Run `link-hoarder COMMAND --help` for full option details. Use `--backend local|api` before the command to select a backend.
Bookmark URLs can use HTTP, HTTPS, or `javascript:` schemes. Link Hoarder stores bookmarklets but does
not execute them. It automatically adds the `bookmarklet` tag to each JavaScript
bookmarklet.

| Command | Purpose |
| --- | --- |
| `create` | Create one bookmark. |
| `list` | List and search bookmarks. |
| `get` | Get one bookmark. |
| `update` | Update supplied bookmark fields. |
| `delete` | Delete one bookmark. |
| `import-browser` | Import Brave, Chrome, Chromium, Edge, Firefox, or Zen profile files. |
| `import-file` | Import a Netscape bookmark HTML export. |
| `config` | Show saved backend configuration without secrets. |
| `api` | Run the HTTP API. |

All bookmark and import commands use the selected backend.
Native browser import files remain on the CLI host.

See [Configure the CLI backend](../how-to/configure-cli-backend.md) for setup and wrapper scripts.
Unix users can open `docs/man/link-hoarder.1` with `man -l`.
