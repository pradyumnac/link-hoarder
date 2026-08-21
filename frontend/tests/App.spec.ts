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

  it("shows browser import warnings with the import summary", async () => {
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

    expect(wrapper.text()).toContain("Warnings: One bookmark is invalid.");
  });

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
  });
});
