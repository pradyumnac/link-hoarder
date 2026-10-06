import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App.vue";
import * as api from "../src/api/client";

vi.mock("../src/api/client", async (loadOriginal) => {
  const original = await loadOriginal<typeof import("../src/api/client")>();
  return {
    ...original,
    createBookmark: vi.fn(),
    deleteBookmark: vi.fn(),
    getBookmarkPreview: vi.fn(),
    importBookmarkFile: vi.fn(),
    importBookmarkJson: vi.fn(),
    listBookmarks: vi.fn(),
    updateBookmark: vi.fn(),
  };
});

const bookmark: api.Bookmark = {
  created_at: "2026-08-21T00:00:00Z",
  folder: "Tools",
  id: 1,
  source: "chrome",
  tags: ["bookmarklet"],
  title: "Reader",
  updated_at: "2026-08-21T00:00:00Z",
  url: "javascript:void(0)",
};

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.cookie = "link_hoarder_variant=; Max-Age=0; Path=/";
    vi.clearAllMocks();
    vi.mocked(api.listBookmarks).mockReset().mockResolvedValue({
      items: [bookmark],
      limit: 10,
      offset: 0,
      total: 1,
    });
    vi.mocked(api.getBookmarkPreview).mockReset().mockResolvedValue({
      bookmark_id: 0,
      description: null,
      image_url: null,
      site_name: null,
      title: null,
    });
  });

  afterEach(() => vi.useRealTimers());

  /** Given focus outside an editable control, slash focuses the primary search field. */
  it("focuses search with the slash shortcut", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    await flushPromises();
    const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "/" });

    document.body.dispatchEvent(event);

    expect(document.activeElement).toBe(wrapper.get('input[aria-label="Search bookmarks"]').element);
    expect(event.defaultPrevented).toBe(true);
    wrapper.unmount();
  });

  /** Given focus in an editable control, slash keeps focus in that control. */
  it("does not override slash in an editable control", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    await flushPromises();
    await wrapper.get(".add-bookmark").trigger("click");
    const titleInput = wrapper.get('input[placeholder="Useful reference"]');
    const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "/" });

    (titleInput.element as HTMLInputElement).focus();
    titleInput.element.dispatchEvent(event);

    expect(document.activeElement).toBe(titleInput.element);
    expect(event.defaultPrevented).toBe(false);
    wrapper.unmount();
  });

  /** Given a 320 px viewport, the compact header keeps each required control present. */
  it("keeps compact-header controls present at the narrow viewport", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 320 });
    const wrapper = mount(App);
    await flushPromises();
    const header = wrapper.get(".app-header");

    expect(header.get("h1").text()).toBe("Link Hoarder");
    expect(header.get(".brand-mark").attributes("src")).toContain("svg");
    expect(header.findAll('input[aria-label="Search bookmarks"]')).toHaveLength(1);
    expect(header.findAll('[aria-label="Add bookmark"]')).toHaveLength(1);
    expect(header.findAll('[aria-label="Import bookmarks"]')).toHaveLength(1);
    expect(header.findAll('[aria-label="UI version"]')).toHaveLength(1);
    expect(header.findAll('[aria-label="Settings"]')).toHaveLength(1);
    expect(header.findAll('[aria-label="Notifications"]')).toHaveLength(1);
    expect(header.find(".search-button").exists()).toBe(false);
  });

  /** Given saved settings, the page restores the default view and page size. */
  it("restores browser settings from local storage", async () => {
    window.localStorage.setItem(
      "link-hoarder.browser-settings",
      JSON.stringify({ accentColor: "#7c3aed", defaultView: "gallery", pageSize: 25 }),
    );
    const items = Array.from({ length: 30 }, (_, index) => ({
      ...bookmark,
      id: index + 1,
      title: `Bookmark ${index + 1}`,
    }));
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items,
      limit: 1000,
      offset: 0,
      total: items.length,
    });

    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.get(".bookmark-list").classes()).toContain("gallery-view");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(25);
    expect(wrapper.get(".pagination").text()).toContain("Page 1 of 2");
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe("#7c3aed");
  });

  /** Given a listed bookmark, the card shows its save date with machine time. */
  it("shows each bookmark save date on its card", async () => {
    const wrapper = mount(App);
    await flushPromises();

    const savedAt = wrapper.get(".bookmark-card .saved-at");
    expect(savedAt.attributes("datetime")).toBe(bookmark.created_at);
    expect(savedAt.attributes("title")).toMatch(/\d{4}/);
    expect(savedAt.text()).toMatch(/\d{4}/);
  });

  /** Given a cached link preview, the card keeps the saved title until preview opens. */
  it("shows the saved title on the card before the preview popup opens", async () => {
    const wrapper = mount(App);
    await flushPromises();
    await flushPromises();

    expect(api.getBookmarkPreview).not.toHaveBeenCalled();
    expect(wrapper.get(".bookmark-card h3").text()).toBe(bookmark.title);
  });

  /** Given a preview button click, the popup shows cached preview text. */
  it("shows the link preview in a popup when the preview button is clicked", async () => {
    const httpBookmark = { ...bookmark, url: "https://example.com/article" };
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [httpBookmark],
      limit: 10,
      offset: 0,
      total: 1,
    });
    vi.mocked(api.getBookmarkPreview).mockResolvedValue({
      bookmark_id: 1,
      description: "Preview description.",
      image_url: null,
      site_name: "Example",
      title: "Preview Title",
    });
    const wrapper = mount(App);
    await flushPromises();
    await flushPromises();

    await wrapper.get(".preview-bookmark").trigger("click");
    await flushPromises();

    expect(api.getBookmarkPreview).toHaveBeenCalledWith(1);
    const popup = wrapper.get(".preview-modal");
    expect(popup.get("#preview-heading").text()).toBe("Preview Title");
    expect(popup.get(".preview-modal-description").text()).toBe(
      "Preview description.",
    );
    const link = popup.get(".bookmark-url");
    expect(link.attributes("href")).toBe("https://example.com/article");
    expect(link.attributes("target")).toBe("_blank");
  });

  /** Given an open preview popup, the close button dismisses it. */
  it("closes the preview popup when the close button is clicked", async () => {
    vi.mocked(api.getBookmarkPreview).mockResolvedValue({
      bookmark_id: 1,
      description: "Preview description.",
      image_url: null,
      site_name: "Example",
      title: "Preview Title",
    });
    const wrapper = mount(App);
    await flushPromises();
    await flushPromises();

    await wrapper.get(".preview-bookmark").trigger("click");
    await flushPromises();
    expect(wrapper.find(".preview-modal").exists()).toBe(true);

    await wrapper.get(".preview-modal-close").trigger("click");

    expect(wrapper.find(".preview-modal").exists()).toBe(false);
  });

  /** Given no version cookie, the top bar identifies stable as the active UI. */
  it("uses the stable UI as the default variant", async () => {
    const wrapper = mount(App);
    await flushPromises();

    const switcher = wrapper.get('[aria-label="UI version"]');
    expect(switcher.get('[aria-current="page"]').text()).toBe("Stable");
    expect(switcher.findAll("a")[1]!.attributes("href")).toContain("version=staging");
  });

  /** Given a staging session cookie, the top bar identifies staging as the active UI. */
  it("restores the staging UI selection from the session cookie", async () => {
    document.cookie = "link_hoarder_variant=staging; Path=/; SameSite=Strict";

    const wrapper = mount(App);
    await flushPromises();

    const switcher = wrapper.get('[aria-label="UI version"]');
    expect(switcher.get('[aria-current="page"]').text()).toBe("Staging");
    expect(switcher.findAll("a")[0]!.attributes("href")).toContain("version=stable");
  });

  /** Given changed settings, the page applies and stores the new values. */
  it("saves browser settings", async () => {
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".settings-button").trigger("click");
    const settingsPanel = wrapper.get(".settings-panel");

    await settingsPanel.get("select").setValue("25");
    await settingsPanel.findAll("select")[1]!.setValue("gallery");

    expect(JSON.parse(window.localStorage.getItem("link-hoarder.browser-settings") ?? "{}")).toEqual({
      accentColor: "#0d684d",
      defaultView: "gallery",
      pageSize: 25,
      sortOrder: "newest",
    });
    expect(wrapper.get(".bookmark-list").classes()).toContain("gallery-view");
  });

  /** Given a selected accent, Settings applies and stores the color. */
  it("saves the selected accent color", async () => {
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".settings-button").trigger("click");

    await wrapper.get('input[aria-label="Accent color"]').setValue("#7c3aed");

    expect(document.documentElement.style.getPropertyValue("--accent")).toBe("#7c3aed");
    expect(document.documentElement.style.getPropertyValue("--accent-contrast")).toBe("#ffffff");
    expect(JSON.parse(window.localStorage.getItem("link-hoarder.browser-settings") ?? "{}")).toEqual({
      accentColor: "#7c3aed",
      defaultView: "list",
      pageSize: 10,
      sortOrder: "newest",
    });
  });

  /** Given a malformed saved accent, the page keeps valid settings and uses green. */
  it("uses green for a malformed saved accent color", async () => {
    window.localStorage.setItem(
      "link-hoarder.browser-settings",
      JSON.stringify({ accentColor: "purple", defaultView: "gallery", pageSize: 25 }),
    );

    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.get(".bookmark-list").classes()).toContain("gallery-view");
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe("#0d684d");
  });

  /** Given malformed saved settings, the page uses safe defaults. */
  it("rejects malformed browser settings", async () => {
    window.localStorage.setItem(
      "link-hoarder.browser-settings",
      JSON.stringify({ defaultView: "tiles", pageSize: -1 }),
    );

    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.get('[aria-label="Show list view"]').attributes("aria-pressed")).toBe("true");
    expect(wrapper.get(".pagination").text()).toContain("Page 1 of 1");
  });

  /** Given rapid query changes, search sends only the final value after the delay. */
  it("searches as the user types", async () => {
    const wrapper = mount(App);
    await flushPromises();
    vi.useFakeTimers();
    const searchInput = wrapper.get('input[aria-label="Search bookmarks"]');

    await searchInput.setValue("read");
    await searchInput.setValue("reader");
    await vi.advanceTimersByTimeAsync(299);

    expect(api.listBookmarks).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(api.listBookmarks).toHaveBeenLastCalledWith("reader", 1000, 0, "newest");
    expect(api.listBookmarks).toHaveBeenCalledTimes(2);
  });

  /** Given an active query, the clear control reloads and focuses unfiltered search. */
  it("clears search with the clear control", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    await flushPromises();
    vi.useFakeTimers();
    const searchInput = wrapper.get('input[aria-label="Search bookmarks"]');

    await searchInput.setValue("reader");
    await vi.advanceTimersByTimeAsync(300);
    await wrapper.get('[aria-label="Clear search"]').trigger("click");
    await flushPromises();

    expect(searchInput.element).toHaveProperty("value", "");
    expect(api.listBookmarks).toHaveBeenLastCalledWith("", 1000, 0, "newest");
    expect(document.activeElement).toBe(searchInput.element);
    expect(wrapper.find('[aria-label="Clear search"]').exists()).toBe(false);
    wrapper.unmount();
  });

  /** Given a failed live search, the interface records and shows the failure. */
  it("reports a search-as-you-type failure", async () => {
    const wrapper = mount(App);
    await flushPromises();
    vi.useFakeTimers();
    vi.mocked(api.listBookmarks).mockRejectedValueOnce(new Error("Search failed"));

    await wrapper.get('input[aria-label="Search bookmarks"]').setValue("reader");
    await vi.advanceTimersByTimeAsync(300);

    expect(wrapper.get('[role="alert"]').text()).toContain("Search failed");
    expect(wrapper.get(".notification-count").text()).toBe("1");
  });

  /** Given bookmarks with different metadata, filters narrow and restore the collection. */
  it("filters bookmarks by tag, type, and folder", async () => {
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [
        bookmark,
        {
          ...bookmark,
          folder: "Research/Reading",
          id: 2,
          source: "manual",
          tags: ["docs"],
          title: "Guide",
          url: "https://github.com/example/guide",
        },
        {
          ...bookmark,
          folder: null,
          id: 3,
          source: "manual",
          tags: [],
          title: "Home",
          url: "https://example.com/",
        },
      ],
      limit: 1000,
      offset: 0,
      total: 3,
    });
    const wrapper = mount(App);
    await flushPromises();

    const library = wrapper.get('nav[aria-label="Library"]');
    const browse = wrapper.get('[aria-label="Browse bookmarks"]');

    expect(library.classes()).toContain("library-destinations");
    expect(library.text()).toContain("All");
    expect(library.text()).toContain("Recent");
    expect(library.text()).toContain("Needs organization");
    expect(library.text()).not.toContain("Bookmarklets");
    expect(browse.text()).toContain("Folders");
    expect(browse.text()).toContain("Tags");
    expect(browse.findAll("details")).toHaveLength(2);
    expect(browse.findAll("details")[0]?.attributes()).not.toHaveProperty("open");
    expect(browse.findAll("details")[1]?.attributes()).not.toHaveProperty("open");
    const sources = wrapper.get('[aria-label="Sources"]');
    expect(sources.attributes()).toHaveProperty("open");
    expect(sources.text()).toBe("SourcesAll sources");
    expect(wrapper.get(".type-filter").attributes()).toHaveProperty("open");
    await wrapper.get('[aria-label="Filter by tag"]').setValue("docs");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Guide");
    await wrapper.get('[aria-label="Filter by tag"]').setValue("");
    await wrapper.get('[aria-label="Filter by bookmark type"]').setValue("bookmarklet");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Reader");
    await wrapper.get('[aria-label="Filter by bookmark type"]').setValue("all");
    const folderInput = wrapper.get('[aria-label="Filter by folder"]');
    await folderInput.setValue("reading");
    expect(wrapper.get(".combobox-options").text()).toContain("Research/Reading");
    expect(wrapper.get(".combobox-options").text()).not.toContain("Tools");
    await folderInput.trigger("focusout", { relatedTarget: null });
    expect(wrapper.find(".combobox-options").exists()).toBe(false);
    await folderInput.trigger("focus");
    await wrapper.get(".combobox-options button").trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Guide");
    await wrapper.get('[aria-label="Filter by folder"]').setValue("");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(3);
  });

  /** Given domain counts, Sources shows only domains with more than five bookmarks. */
  it("shows and selects frequent bookmark sources", async () => {
    const githubBookmarks = Array.from({ length: 6 }, (_, index) => ({
      ...bookmark,
      id: index + 1,
      title: `GitHub ${index + 1}`,
      favicon_url: `/api/v1/bookmarks/${index + 1}/favicon`,
      thumbnail_url: null,
      url: `https://github.com/example/${index + 1}`,
    }));
    const youtubeBookmarks = Array.from({ length: 5 }, (_, index) => ({
      ...bookmark,
      id: index + 7,
      title: `YouTube ${index + 1}`,
      url: `https://youtube.com/watch?v=${index + 1}`,
    }));
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [...githubBookmarks, ...youtubeBookmarks],
      limit: 1000,
      offset: 0,
      total: 11,
    });
    const wrapper = mount(App);
    await flushPromises();
    const sources = wrapper.get('[aria-label="Sources"]');

    expect(sources.text()).toContain("GitHub6");
    expect(sources.text()).not.toContain("YouTube");
    expect(sources.get('.source-name img').attributes("src")).toBe(
      "/api/v1/bookmarks/1/favicon",
    );
    await wrapper.get('[data-source="github.com"]').trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(6);
    expect(wrapper.text()).toContain("GitHub 1");
    expect(wrapper.text()).not.toContain("YouTube 1");
  });

  /** Given smart Library destinations, Recent and Needs organization select useful subsets. */
  it("selects smart Library destinations", async () => {
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [
        { ...bookmark, created_at: new Date().toISOString(), title: "Recent organized" },
        {
          ...bookmark,
          created_at: "2000-01-01T00:00:00Z",
          folder: null,
          id: 2,
          tags: [],
          title: "Old unorganized",
          url: "https://example.com/old",
        },
      ],
      limit: 1000,
      offset: 0,
      total: 2,
    });
    const wrapper = mount(App);
    await flushPromises();

    await wrapper.get('[data-library-destination="needs-organization"]').trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Old unorganized");
    await wrapper.get('[data-library-destination="recent"]').trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Recent organized");
  });

  /** Given narrow navigation, its controls open and the backdrop closes the drawer. */
  it("opens and closes the collection navigation drawer", async () => {
    const wrapper = mount(App);
    await flushPromises();
    const toggle = wrapper.get('[aria-label="Open collection navigation"]');
    const navigation = wrapper.get('[aria-label="Collection navigation"]');

    expect(toggle.element.closest(".app-header")).not.toBeNull();
    expect(toggle.classes()).toContain("icon-button");
    expect(toggle.classes()).toContain("secondary");
    expect(toggle.get("svg path").attributes("d")).toContain("M4 6h16");
    expect(navigation.find(".drawer-heading strong").exists()).toBe(false);
    const drawerActions = navigation.get('[aria-label="Mobile actions"]');
    const drawerImport = drawerActions.get('[aria-label="Import bookmarks"]');
    const drawerSettings = drawerActions.get('[aria-label="Settings"]');
    expect(drawerImport.classes()).toContain("icon-button");
    expect(drawerSettings.classes()).toContain("icon-button");
    expect(drawerImport.get("svg path").attributes("d")).toContain("M14 3H7");
    expect(drawerSettings.get("svg path").attributes("d")).toContain("M4 21v-7");
    expect(toggle.attributes("aria-expanded")).toBe("false");
    expect(navigation.classes()).not.toContain("open");
    expect(wrapper.find(".navigation-backdrop").exists()).toBe(false);
    await toggle.trigger("click");
    expect(toggle.attributes("aria-expanded")).toBe("true");
    expect(navigation.classes()).toContain("open");
    await wrapper.get(".navigation-backdrop").trigger("click");
    expect(toggle.attributes("aria-expanded")).toBe("false");
    expect(navigation.classes()).not.toContain("open");
  });

  /** Given nested folders, folder links drill down and breadcrumbs return to the root. */
  it("navigates the folder hierarchy with breadcrumbs", async () => {
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [
        bookmark,
        {
          ...bookmark,
          folder: "Research/Reading",
          id: 2,
          tags: ["docs"],
          title: "Guide",
          url: "https://example.com/guide",
        },
        {
          ...bookmark,
          folder: "Research/Archive",
          id: 3,
          tags: [],
          title: "Archive",
          url: "https://example.com/archive",
        },
      ],
      limit: 1000,
      offset: 0,
      total: 3,
    });
    const wrapper = mount(App);
    await flushPromises();

    await wrapper.get('.folder-link[data-folder="Research"]').trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(2);
    expect(wrapper.get(".breadcrumbs").text()).toContain("Research");
    await wrapper.get('.folder-link[data-folder="Research/Reading"]').trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Guide");
    await wrapper.get('.breadcrumb-link[data-folder=""]').trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(3);
  });

  /** Given the collection, the user can change between list and gallery views. */
  it("changes the bookmark collection view", async () => {
    const wrapper = mount(App);
    await flushPromises();
    const listButton = wrapper.get('[aria-label="Show list view"]');
    const galleryButton = wrapper.get('[aria-label="Show gallery view"]');

    expect(listButton.attributes("aria-pressed")).toBe("true");
    expect(wrapper.get(".bookmark-list").classes()).toContain("list-view");
    await galleryButton.trigger("click");
    expect(galleryButton.attributes("aria-pressed")).toBe("true");
    expect(wrapper.get(".bookmark-list").classes()).toContain("gallery-view");
    expect(wrapper.text()).toContain("Reader");
    await listButton.trigger("click");
    expect(wrapper.get(".bookmark-list").classes()).toContain("list-view");
  });

  /** Given cached presentation assets, cards use concise links, icons, and gallery thumbnails. */
  it("presents bookmark metadata from same-origin assets", async () => {
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [
        {
          ...bookmark,
          favicon_url: "/api/v1/bookmarks/2/favicon",
          id: 2,
          thumbnail_url: "/api/v1/bookmarks/2/thumbnail",
          title: "Long guide",
          url: "https://docs.example.com/reference/a-long-path/?token=secret#section",
        },
      ],
      limit: 1000,
      offset: 0,
      total: 1,
    });
    const wrapper = mount(App);
    await flushPromises();
    const link = wrapper.get(".bookmark-copy a");

    expect(link.text()).toBe("docs.example.com/reference/a-long-path");
    expect(link.attributes("href")).toContain("?token=secret#section");
    expect(link.attributes("aria-label")).toContain("?token=secret#section");
    expect(link.attributes("title")).toContain("?token=secret#section");
    expect(wrapper.get(".bookmark-icon").attributes("src")).toBe(
      "/api/v1/bookmarks/2/favicon",
    );
    expect(wrapper.find(".bookmark-thumbnail").exists()).toBe(false);

    await wrapper.get('[aria-label="Show gallery view"]').trigger("click");
    const thumbnail = wrapper.get(".bookmark-thumbnail img");
    expect(thumbnail.attributes("src")).toBe("/api/v1/bookmarks/2/thumbnail");
    await thumbnail.trigger("error");
    // The media area stays in place after a failed thumbnail load, so gallery
    // cards keep a consistent height. It falls back to the brand mark instead
    // of leaving an empty region.
    expect(wrapper.find(".bookmark-thumbnail").exists()).toBe(true);
    // The fallback reuses the bookmark's own favicon, which the API backs
    // with a generated per-domain icon, so each card stays distinct.
    expect(wrapper.get(".bookmark-thumbnail-fallback").attributes("src")).toBe(
      "/api/v1/bookmarks/2/favicon",
    );
  });

  /** Given a bookmark with no thumbnail at all, the gallery card still reserves a media area. */
  it("shows a fallback media area for bookmarks without a thumbnail", async () => {
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [
        {
          ...bookmark,
          id: 3,
          thumbnail_url: null,
          favicon_url: "/api/v1/bookmarks/3/favicon",
          url: "https://example.com/reading",
        },
      ],
      limit: 1000,
      offset: 0,
      total: 1,
    });
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get('[aria-label="Show gallery view"]').trigger("click");

    expect(wrapper.findAll(".bookmark-thumbnail img")).toHaveLength(1);
    expect(wrapper.get(".bookmark-thumbnail-fallback").attributes("src")).toBe(
      "/api/v1/bookmarks/3/favicon",
    );
  });

  /** Given a bookmark with neither a thumbnail nor a favicon, the card falls back to the brand mark. */
  it("falls back to the brand mark when a bookmark has no favicon", async () => {
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [{ ...bookmark, id: 5, thumbnail_url: null, url: "https://example.com/plain" }],
      limit: 1000,
      offset: 0,
      total: 1,
    });
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get('[aria-label="Show gallery view"]').trigger("click");

    // A dynamic binding keeps the public asset path as written, while the
    // header uses a static src that the bundler may inline.
    expect(wrapper.get(".bookmark-thumbnail-fallback").attributes("src")).toBe(
      "/link-hoarder.svg",
    );
  });

  /** Given a long URL, the gallery card truncates it to one line and keeps the full URL for the link and tooltip. */
  it("truncates a long URL on one line in the gallery view", async () => {
    const longUrl =
      "https://community-scripts.github.io/ProxmoxVE/scripts?id=proxmox-ve-helper-scripts";
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [{ ...bookmark, id: 4, thumbnail_url: null, url: longUrl }],
      limit: 1000,
      offset: 0,
      total: 1,
    });
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get('[aria-label="Show gallery view"]').trigger("click");
    const link = wrapper.get(".bookmark-url");

    // The `.bookmark-url` class carries the single-line ellipsis truncation
    // rule in style.css. The full URL stays available as the link target and
    // as a hover tooltip.
    expect(link.attributes("href")).toBe(longUrl);
    expect(link.attributes("title")).toBe(longUrl);
  });

  /** Given header actions, Add and Import use labeled purpose-specific vector icons. */
  it("uses accessible header action icons", async () => {
    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.get('[aria-label="Settings"] path').attributes("d")).toContain("M4 21v-7");
    expect(wrapper.get('[aria-label="Add bookmark"]').classes()).toContain("secondary");
    expect(wrapper.get('[aria-label="Import bookmarks"]').classes()).toContain("secondary");
    expect(wrapper.get('[aria-label="Add bookmark"] path').attributes("d")).toContain(
      "M19 21l-7-5-7 5",
    );
    expect(wrapper.get('[aria-label="Import bookmarks"] path').attributes("d")).toContain(
      "M14 3H7",
    );
    expect(wrapper.get('[aria-label="Edit Reader"]').text()).toBe("✎");
    const deleteAction = wrapper.get('[aria-label="Delete Reader"]');
    expect(deleteAction.classes()).not.toContain("danger");
    expect(deleteAction.get("path").attributes("d")).toContain("M3 6h18");
    await wrapper.get(".import-bookmarks").trigger("click");
    expect(wrapper.get('[aria-label="Close import"]').text()).toBe("×");
  });

  /** Given an open header panel, inside interaction keeps it open and outside click closes it. */
  it("dismisses header panels on outside click", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    await flushPromises();

    await wrapper.get(".settings-button").trigger("click");
    wrapper.get(".settings-panel").element.dispatchEvent(
      new MouseEvent("pointerdown", { bubbles: true }),
    );
    expect(wrapper.find(".settings-panel").exists()).toBe(true);
    document.body.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".settings-panel").exists()).toBe(false);

    await wrapper.get(".notification-button").trigger("click");
    wrapper.get(".notification-panel").element.dispatchEvent(
      new MouseEvent("pointerdown", { bubbles: true }),
    );
    expect(wrapper.find(".notification-panel").exists()).toBe(true);
    document.body.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".notification-panel").exists()).toBe(false);
    wrapper.unmount();
  });

  /** Given a visible alert or notice, its Unicode close button dismisses it. */
  it("dismisses browser messages", async () => {
    vi.mocked(api.listBookmarks).mockRejectedValueOnce(new Error("Load failed"));
    const wrapper = mount(App);
    await flushPromises();

    await wrapper.get('[aria-label="Dismiss alert"]').trigger("click");
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    await wrapper.get(".settings-button").trigger("click");
    await wrapper.get(".settings-panel select").setValue("25");
    await wrapper.get('[aria-label="Dismiss notice"]').trigger("click");
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
  });

  it("shows imported bookmarklets with an identifying badge", async () => {
    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.text()).toContain("Reader");
    expect(wrapper.find(".bookmarklet").text()).toBe("Bookmarklet");
    expect(wrapper.find(".bookmark-card a").exists()).toBe(false);
  });

  /** Given the collection, the create action opens a bookmark modal. */
  it("opens and closes the create bookmark modal", async () => {
    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    await wrapper.get(".add-bookmark").trigger("click");
    expect(wrapper.get('[role="dialog"]').attributes("aria-modal")).toBe("true");
    await wrapper.get(".modal-close").trigger("click");
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
  });

  /** Given a saved bookmark, Edit opens a populated modal that can be cancelled. */
  it("opens the edit bookmark modal", async () => {
    const wrapper = mount(App);
    await flushPromises();

    await wrapper.get(".edit-bookmark").trigger("click");

    expect(wrapper.get('input[placeholder="Useful reference"]').element).toHaveProperty(
      "value",
      "Reader",
    );
    expect(wrapper.get('input[placeholder="Research/Reading"]').element).toHaveProperty(
      "value",
      "Tools",
    );
    await wrapper.get(".modal-close").trigger("click");
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
  });

  it("creates a bookmark and reloads the collection", async () => {
    vi.mocked(api.createBookmark).mockResolvedValue({
      ...bookmark,
      source: "manual",
      title: "Example",
      url: "https://example.com/",
    });
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".add-bookmark").trigger("click");

    await wrapper.get('input[placeholder="https://example.com"]').setValue("https://example.com");
    await wrapper.get('input[placeholder="Useful reference"]').setValue("Example");
    await wrapper.get(".bookmark-form").trigger("submit");
    await flushPromises();

    expect(api.createBookmark).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Example", url: "https://example.com" }),
    );
    expect(wrapper.text()).toContain("Bookmark created.");
  });

  /** Given the initial view, the Import icon opens a modal that can be closed. */
  it("opens and closes the import modal", async () => {
    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.find(".import-form").exists()).toBe(false);
    await wrapper.get(".import-bookmarks").trigger("click");
    expect(wrapper.get(".import-modal").attributes("aria-modal")).toBe("true");
    expect(wrapper.find(".import-form").exists()).toBe(true);
    await wrapper.get(".import-modal-close").trigger("click");
    expect(wrapper.find(".import-form").exists()).toBe(false);
  });

  /** Given an import warning, the notification center shows one unread failure event. */
  it("shows browser import warnings in the notification center", async () => {
    vi.mocked(api.importBookmarkFile).mockResolvedValue({
      format: "netscape_html",
      discovered: 1,
      imported: 0,
      profiles: 1,
      skipped: 0,
      warnings: [
        {
          code: "bookmark_invalid",
          message: "One bookmark is invalid.",
          profile: "Bookmarks",
        },
      ],
    });
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".settings-button").trigger("click");
    await wrapper.get('input[aria-label="Accent color"]').setValue("#7c3aed");
    await wrapper.get(".import-bookmarks").trigger("click");
    const input = wrapper.get('input[type="file"]');
    const file = new File(["profile"], "Bookmarks");
    Object.defineProperty(input.element, "files", { value: [file] });

    await input.trigger("change");
    await wrapper.get(".import-form").trigger("submit");
    await flushPromises();

    expect(wrapper.get(".notification-count").text()).toBe("2");
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe("#7c3aed");
    await wrapper.get(".notification-button").trigger("click");
    expect(wrapper.get(".notification-list li").classes()).toContain("unread");
    expect(wrapper.get(".notification-list").text()).toContain("Imported 0; skipped 0.");
    expect(wrapper.get(".notification-list").text()).toContain("One bookmark is invalid.");
    expect(wrapper.get(".notice").text()).toContain("1 warning is in Notifications.");
  });

  /** Given one unread event, the user can mark it as read and clear it. */
  it("manages notification read and clear state", async () => {
    vi.mocked(api.importBookmarkFile).mockRejectedValue(new Error("Import failed"));
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".import-bookmarks").trigger("click");
    const input = wrapper.get('input[type="file"]');
    Object.defineProperty(input.element, "files", {
      value: [new File(["profile"], "Bookmarks")],
    });

    await input.trigger("change");
    await wrapper.get(".import-form").trigger("submit");
    await flushPromises();
    await wrapper.get(".notification-button").trigger("click");
    await wrapper.get(".mark-read").trigger("click");

    expect(wrapper.find(".notification-count").exists()).toBe(false);
    await wrapper.get(".clear-notification").trigger("click");
    expect(wrapper.get(".notification-panel").text()).toContain("No events.");
  });

  /** Given a failed create request, the event is recorded and bookmarks remain visible. */
  it("shows an API failure without removing the current collection", async () => {
    vi.mocked(api.createBookmark).mockRejectedValue(new Error("URL conflict"));
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".add-bookmark").trigger("click");

    await wrapper.get('input[placeholder="https://example.com"]').setValue("https://example.com");
    await wrapper.get('input[placeholder="Useful reference"]').setValue("Duplicate");
    await wrapper.get(".bookmark-form").trigger("submit");
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain("URL conflict");
    expect(wrapper.text()).toContain("Reader");
    expect(wrapper.get(".notification-count").text()).toBe("1");
  });

  /** Given no selected file, an import attempt creates a failure event. */
  it("records missing import file validation", async () => {
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".import-bookmarks").trigger("click");

    await wrapper.get(".import-form").trigger("submit");

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "Select a bookmark HTML or JSON export file.",
    );
    expect(wrapper.get(".notification-count").text()).toBe("1");
  });

  /** Given a JSON export file, the import uses the JSON endpoint. */
  it("sends a JSON export to the JSON import endpoint", async () => {
    vi.mocked(api.importBookmarkJson).mockResolvedValue({
      format: "link_hoarder_json",
      discovered: 1,
      imported: 1,
      profiles: 1,
      skipped: 0,
      warnings: [],
    });
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".import-bookmarks").trigger("click");
    const input = wrapper.get('input[type="file"]');
    const file = new File(["[]"], "bookmarks.json", { type: "application/json" });
    Object.defineProperty(input.element, "files", { value: [file] });

    await input.trigger("change");
    await wrapper.get(".import-form").trigger("submit");
    await flushPromises();

    expect(api.importBookmarkJson).toHaveBeenCalledWith(file);
    expect(api.importBookmarkFile).not.toHaveBeenCalled();
    expect(wrapper.get(".notice").text()).toContain("Imported 1; skipped 0.");
  });

  /** Given an HTML export file, the import keeps using the HTML endpoint. */
  it("sends an HTML export to the HTML import endpoint", async () => {
    vi.mocked(api.importBookmarkFile).mockResolvedValue({
      format: "netscape_html",
      discovered: 1,
      imported: 1,
      profiles: 1,
      skipped: 0,
      warnings: [],
    });
    const wrapper = mount(App);
    await flushPromises();
    await wrapper.get(".import-bookmarks").trigger("click");
    const input = wrapper.get('input[type="file"]');
    const file = new File(["<DL><p>"], "bookmarks.html", { type: "text/html" });
    Object.defineProperty(input.element, "files", { value: [file] });

    await input.trigger("change");
    await wrapper.get(".import-form").trigger("submit");
    await flushPromises();

    expect(api.importBookmarkFile).toHaveBeenCalledWith(file);
    expect(api.importBookmarkJson).not.toHaveBeenCalled();
  });

  /** Given the collection, the sort picker reloads bookmarks in save-time order. */
  it("reloads bookmarks in the selected sort order", async () => {
    const wrapper = mount(App);
    await flushPromises();

    expect(vi.mocked(api.listBookmarks).mock.calls[0]?.[3]).toBe("newest");

    await wrapper.get('[aria-label="Sort oldest first"]').trigger("click");
    await flushPromises();

    const calls = vi.mocked(api.listBookmarks).mock.calls;
    expect(calls[calls.length - 1]?.[3]).toBe("oldest");
    const stored = window.localStorage.getItem("link-hoarder.browser-settings") ?? "{}";
    expect((JSON.parse(stored) as { sortOrder: string }).sortOrder).toBe("oldest");
    expect(wrapper.get('[aria-label="Sort oldest first"]').attributes("aria-pressed")).toBe("true");
  });
});
