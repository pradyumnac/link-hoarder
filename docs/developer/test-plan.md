# Test plan

## Primary flows

- Create, read, list, update, and delete a bookmark.
- Import bookmarks from Chromium and Firefox profile files through the CLI.
- Import a Netscape bookmark HTML export through the CLI and API.
- Use CRUD and import features through each supported interface.
- Build the Python package and container image.

## Alternate flows

- Filter the bookmark list.
- Import a profile that contains an existing URL.
- Select an explicit browser profile path.
- Import an HTML export that contains an existing URL.

## Edge flows

- Import nested Chromium and HTML export folders.
- Import a Firefox bookmark without a folder title.
- Return an empty list when no bookmarks exist.

## Negative flows

- Reject an invalid bookmark URL.
- Return a not-found result for an unknown identifier.
- Reject API requests with a missing or invalid API key.
- Warn about a missing or malformed browser profile or HTML export.
