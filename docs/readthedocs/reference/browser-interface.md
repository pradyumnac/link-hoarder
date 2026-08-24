# Browser interface reference

The browser interface provides bookmark management through the HTTP API.

## Collection actions

The Add and Import icons are to the right of the search box.
Add, Import, Settings, and Notifications use matching backgrounds.
Their backgrounds use the selected accent color on hover.
The Add, Import, Settings, and Notifications SVGs use the same size and stroke width.
Each icon has an accessible label.

| Icon | Action |
| --- | --- |
| Bookmark with plus | Open the bookmark creation dialog. |
| Arrow entering a file | Open the bookmark HTML import dialog. |
| Pencil | Open the selected bookmark for editing. |
| Red outline trash | Delete a bookmark. |
| Cross | Close a message or dialog. |

Search runs after the user stops typing. Press Enter to run it immediately.

## Test UI selection

The opt-in A/B stack shows Stable and Staging controls in the top bar.
The normal interface does not show these test controls.
See [A/B Switching](../how-to/ab-switching.md) for the redesign workflow.

## Collection navigation

The left pane provides these controls:

- List and gallery views.
- Tag filtering.
- Bookmark and bookmarklet type filtering.
- A searchable folder dropdown.
- Child folder navigation.

Breadcrumbs above the collection show the selected folder hierarchy.
Selecting a parent folder includes bookmarks from its child folders.

## Dialogs and notifications

Creation, editing, and bookmark HTML import use modal dialogs.
The Notifications icon opens the event list.
The Settings icon is beside the Notifications icon.
Click outside an open Settings or Notifications panel to close it.
Settings contains an accent color picker. The default accent color is green.

Import warnings and failed operations create notification events.
Status messages and unread events use the selected accent color.
Error alerts remain red.
Alerts and status notices also have a close icon.

## Layout

The interface adapts to mobile, tablet, desktop, wide desktop, and 4K screens.
Wide layouts show more bookmark cards while text keeps a readable width.

See [Browser settings](configuration.md#browser-settings) for saved display settings.
