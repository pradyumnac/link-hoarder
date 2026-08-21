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
    importBookmarkFile: vi.fn(),
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
    vi.clearAllMocks();
    vi.mocked(api.listBookmarks).mockReset().mockResolvedValue({
      items: [bookmark],
      limit: 10,
      offset: 0,
      total: 1,
    });
  });

  afterEach(() => vi.useRealTimers());

  /** Given saved settings, the page restores the default view and page size. */
  it("restores browser settings from local storage", async () => {
    window.localStorage.setItem(
      "link-hoarder.browser-settings",
      JSON.stringify({ defaultView: "gallery", pageSize: 25 }),
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
      defaultView: "gallery",
      pageSize: 25,
    });
    expect(wrapper.get(".bookmark-list").classes()).toContain("gallery-view");
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
    expect(api.listBookmarks).toHaveBeenLastCalledWith("reader", 1000, 0);
    expect(api.listBookmarks).toHaveBeenCalledTimes(2);
  });

  /** Given an active query, clearing the input reloads the unfiltered collection. */
  it("reloads bookmarks when the user clears search", async () => {
    const wrapper = mount(App);
    await flushPromises();
    vi.useFakeTimers();
    const searchInput = wrapper.get('input[aria-label="Search bookmarks"]');

    await searchInput.setValue("reader");
    await vi.advanceTimersByTimeAsync(300);
    await searchInput.setValue("");
    await vi.advanceTimersByTimeAsync(300);

    expect(api.listBookmarks).toHaveBeenLastCalledWith("", 1000, 0);
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
          url: "https://example.com/guide",
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

    await wrapper.get('[aria-label="Filter by tag"]').setValue("docs");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Guide");
    await wrapper.get('[aria-label="Filter by tag"]').setValue("");
    await wrapper.get('[aria-label="Filter by bookmark type"]').setValue("bookmarklet");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Reader");
    await wrapper.get('[aria-label="Filter by bookmark type"]').setValue("all");
    await wrapper.get('[aria-label="Filter by folder"]').setValue("reading");
    expect(wrapper.get(".combobox-options").text()).toContain("Research/Reading");
    expect(wrapper.get(".combobox-options").text()).not.toContain("Tools");
    await wrapper.get(".combobox-options button").trigger("click");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("Guide");
    await wrapper.get('[aria-label="Filter by folder"]').setValue("");
    expect(wrapper.findAll(".bookmark-card")).toHaveLength(3);
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

  /** Given bookmark and search actions, Unicode icons retain accessible labels. */
  it("uses accessible Unicode action icons", async () => {
    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.get('[aria-label="Settings"]').text()).toBe("⚙");
    expect(wrapper.get(".search-button").text()).toBe("⌕");
    expect(wrapper.get('[aria-label="Add bookmark"]').text()).toBe("＋");
    expect(wrapper.get('[aria-label="Import bookmarks"]').text()).toBe("⇩");
    expect(wrapper.get('[aria-label="Edit Reader"]').text()).toBe("✎");
    expect(wrapper.get('[aria-label="Delete Reader"]').text()).toBe("×");
    await wrapper.get(".import-bookmarks").trigger("click");
    expect(wrapper.get('[aria-label="Close import"]').text()).toBe("×");
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
    expect(wrapper.find("a").exists()).toBe(false);
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
    await wrapper.get(".import-bookmarks").trigger("click");
    const input = wrapper.get('input[type="file"]');
    const file = new File(["profile"], "Bookmarks");
    Object.defineProperty(input.element, "files", { value: [file] });

    await input.trigger("change");
    await wrapper.get(".import-form").trigger("submit");
    await flushPromises();

    expect(wrapper.get(".notification-count").text()).toBe("2");
    await wrapper.get(".notification-button").trigger("click");
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
      "Select a bookmark HTML export file.",
    );
    expect(wrapper.get(".notification-count").text()).toBe("1");
  });
});
