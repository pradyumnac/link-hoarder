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

The Library section provides these destinations:

- All.
- Recent items from the last 30 days.
- Items that need a folder or tag.

The collapsible Sources section starts expanded.
It shows website domains that contain more than five bookmarks.
Each source shows its item count.
Known domains use names such as GitHub, YouTube, and Reddit.
The Browse section puts folder and tag controls in separate collapsible groups.
The Folders and Tags groups start collapsed.
The folder results close when focus leaves the folder control.
The Filters section starts expanded and provides bookmark type filtering.
The View section provides list and gallery views.

On narrow screens, the header menu opens these controls in a navigation drawer.
Add and Notifications remain in the header.
Import and Settings move into a subtle icon row below the drawer close button.

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
The centered workspace stays at or below 3400 px.
Desktop collection navigation scales from 260 px to 360 px.
Gallery columns fit the available results width while each card keeps a readable minimum width.

See [Browser settings](configuration.md#browser-settings) for saved display settings.
