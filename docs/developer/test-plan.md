# Test plan

## Primary flows

- Create, read, list, update, and delete a bookmark.
- Import bookmarks from Chromium and Firefox profile files through the CLI.
- Import a Netscape bookmark HTML export through the CLI and API.
- Use CRUD and import features through the local SQLite and HTTP CLI backends.
- Save each setup mode and install all user wrapper scripts.
- Start the local API with Docker Compose during local API setup.
- Build the Python package and container image.

## Alternate flows

- Filter the bookmark list.
- Import a profile that contains an existing URL.
- Select an explicit browser profile path.
- Import an HTML export that contains an existing URL.
- Override the saved backend with an environment variable or `--backend`.
- Configure an existing remote API instead of a local API.

## Edge flows

- Import nested Chromium and HTML export folders.
- Import a Firefox bookmark without a folder title.
- Return an empty list when no bookmarks exist.
- Encode a full bookmark URL in an API lookup query.
- Keep API keys out of configuration and setup output.

## Negative flows

- Reject an invalid bookmark URL.
- Return a not-found result for an unknown identifier.
- Reject API requests with a missing or invalid API key.
- Warn about a missing or malformed browser profile or HTML export.
- Reject an incomplete or malformed saved API configuration.
- Report API authentication, connection, and response failures without a traceback.
- Report a Docker Compose startup failure.
