# Manage bookmarks in the web interface

Start the Docker stack and open `http://127.0.0.1:8080`.

```console
mise run stack-up
```

## Search for bookmarks

Type in the search box. The collection updates after you stop typing.
Select the Search icon to run the search immediately.

Use the filters in the left pane to limit the collection by tag or bookmark type.
Type in the folder field, then select a matching folder from the dropdown.
Use folder links to move to a child folder.
Use the breadcrumbs to return to a parent folder.

## Change the collection view

Select **List** or **Gallery** in the left pane.
The web interface saves your selected view as the default view.

Select the Settings icon beside Notifications to change the page size.
See the [configuration reference](../reference/configuration.md#browser-settings) for all browser settings.

## Add or edit a bookmark

Select the Add icon to open the bookmark form.
Enter the URL, title, folder, and tags.
Select **Save bookmark**.

Select the Edit icon on a bookmark to open the populated form.
Change the values, then select **Save changes**.

## Import bookmark HTML

Select the Import icon to open the import dialog.
Select a Netscape bookmark HTML export file.
Select **Import bookmarks**.

The notification panel shows import warnings and completion events.
Select the close icon on an alert, notice, or dialog to dismiss it.
