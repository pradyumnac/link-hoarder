# Test plan

## Primary flows

- Create, read, list, update, and delete a bookmark.
- Import bookmarks from Chromium, Firefox, Brave, and Zen profile files through the CLI.
- Import a Netscape bookmark HTML export through the CLI and API.
- Export all bookmarks to Netscape HTML and JSON subdirectories through the CLI.
- Report clear completion feedback for each successful mutating CLI command.
- Write debug checkpoints to standard error when the global debug switch is active.
- Show readable list and get output by default.
- Show structured list and get output when the JSON switch is active.
- Use CRUD and import features through the local SQLite and HTTP CLI backends.
- Save each setup mode and install all user wrapper scripts.
- Start the local API with Docker Compose during local API setup.
- Build the Python package and container image.
- Show import summaries and warnings in the browser notification center.
- Update browser search results after the user types a query.
- Open the browser import modal when the user selects the Import icon.
- Change the bookmark collection from list view to gallery view.
- Filter browser bookmarks by tag, bookmark type, and folder.
- Navigate from the root folder to a nested folder in the browser interface.
- Save the page size and default collection view in browser-local storage.
- Open a modal dialog to create a bookmark.
- Use Unicode icon buttons to add, search, import, edit, delete, close controls, and dismiss alerts.
- Type a folder query and select a matching folder from the dropdown.

## Alternate flows

- Filter the bookmark list.
- Import a profile that contains an existing URL.
- Select an explicit browser profile path for each supported browser family.
- Override the saved export directory for one export.
- Reuse the saved export directory as the next interactive default.
- Report a clear cancellation message when the user declines an overwrite.
- Keep debug checkpoints disabled during normal CLI use.
- Report an empty list in readable text and as an empty JSON array.
- Import an HTML export that contains an existing URL.
- Override the saved backend with an environment variable or `--backend`.
- Configure an existing remote API instead of a local API.
- Record failed create, update, delete, list, and import operations as notification events.
- Record duplicate imports as warning events.
- Reload all browser bookmarks after the user clears the search query.
- Close the browser import modal without starting an import.
- Change the bookmark collection from gallery view to list view.
- Clear each browser bookmark filter to show all search results.
- Use folder breadcrumbs to return to a parent folder or all folders.
- Restore saved browser settings when the user reloads the page.
- Open a populated modal dialog to edit a bookmark.
- Provide an accessible label for each Unicode icon button.
- Keep the Add, Search, and Import icons to the right of the search box.
- Keep the Settings icon beside the Notifications icon.
- Clear the folder query to return to all folders.

## Edge flows

- Import nested Chromium and HTML export folders.
- Export nested folders, bookmarklets, and an empty collection.
- Report when native profile discovery finds no profiles.
- Keep API keys and bookmark content out of debug checkpoints.
- Discover Brave and Zen profiles in standard Windows and Linux directories.
- Read a stable Zen snapshot while its SQLite database uses write-ahead logging.
- Include later Zen bookmark additions only in the next import snapshot.
- Import a Firefox bookmark without a folder title.
- Return an empty list when no bookmarks exist.
- Encode a full bookmark URL in an API lookup query.
- Keep API keys out of configuration and setup output.
- Mark all notification events as read and clear one event.
- Show the import summary when an import has no warnings.
- Send only the final browser search query when the user types multiple characters quickly.
- Hide the browser import modal on initial load.
- Keep all bookmark actions available in list and gallery views.
- Combine tag, bookmark type, and folder filters.
- Include direct and nested bookmarks when the user selects a parent folder.
- Use default browser settings when browser-local storage has no saved settings.
- Close a bookmark modal without saving its values.
- Dismiss error and status messages independently.
- Match folder queries without case sensitivity.

## Negative flows

- Use exit code 1 when an action is valid but does not complete or change state.
- Use exit code 2 for invalid input, configuration, storage, and connection failures.
- Report expected CLI failures without a traceback.

- Reject an invalid bookmark URL.
- Return a not-found result for an unknown identifier.
- Reject API requests with a missing or invalid API key.
- Warn about a missing or malformed Brave, Zen, or other browser profile.
- Refuse an overwrite without confirmation or force mode.
- Require an export directory when non-interactive mode has no saved default.
- Reject an incomplete or malformed saved API configuration.
- Report API authentication, connection, and response failures without a traceback.
- Report a Docker Compose startup failure.
- Record an import attempt that has no selected file.
- Show a notification event when a browser search request fails.
- Keep the browser import modal open when an import attempt has no selected file.
- Keep one collection view selected when the user selects the active view again.
- Disable filter choices when the loaded collection has no applicable values.
- Hide child folder links when the selected folder has no child folders.
- Reject malformed browser settings and report browser-local storage write failures.
- Keep invalid bookmark form values in the open modal for correction.
- Keep icon-only actions understandable when their visible text is not available.
- Show an empty dropdown state when no folder matches the typed query.
