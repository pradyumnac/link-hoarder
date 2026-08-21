# Test plan

## Primary flows

- Create, read, list, update, and delete a bookmark.
- Import bookmarks from Chromium and Firefox profile files.
- Use CRUD and import features through the CLI and API.
- Build the Python package and container image.

## Alternate flows

- Filter the bookmark list.
- Import a profile that contains an existing URL.
- Select an explicit browser profile path.

## Edge flows

- Import nested Chromium folders.
- Import a Firefox bookmark without a folder title.
- Return an empty list when no bookmarks exist.

## Negative flows

- Reject an invalid bookmark URL.
- Return a not-found result for an unknown identifier.
- Reject API requests with a missing or invalid API key.
- Reject a missing or malformed browser profile.
