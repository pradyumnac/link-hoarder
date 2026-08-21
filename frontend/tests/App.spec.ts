import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
    vi.mocked(api.listBookmarks).mockResolvedValue({
      items: [bookmark],
      limit: 10,
      offset: 0,
      total: 1,
    });
  });

  it("shows imported bookmarklets with an identifying badge", async () => {
    const wrapper = mount(App);
    await flushPromises();

    expect(wrapper.text()).toContain("Reader");
    expect(wrapper.find(".bookmarklet").text()).toBe("Bookmarklet");
    expect(wrapper.find("a").exists()).toBe(false);
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

    await wrapper.get('input[placeholder="https://example.com"]').setValue("https://example.com");
    await wrapper.get('input[placeholder="Useful reference"]').setValue("Example");
    await wrapper.get(".bookmark-form").trigger("submit");
    await flushPromises();

    expect(api.createBookmark).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Example", url: "https://example.com" }),
    );
    expect(wrapper.text()).toContain("Bookmark created.");
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

    await wrapper.get(".import-form").trigger("submit");

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "Select a bookmark HTML export file.",
    );
    expect(wrapper.get(".notification-count").text()).toBe("1");
  });
});
