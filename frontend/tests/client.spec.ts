import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getBookmarkPreview,
  importBookmarkFile,
  importBookmarkJson,
  listBookmarks,
} from "../src/api/client";

describe("API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends pagination and search through the versioned endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], limit: 10, offset: 20, total: 0 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listBookmarks("tools", 10, 20);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/bookmarks?limit=10&offset=20&query=tools",
      undefined,
    );
  });

  it("uploads bookmark HTML to the export endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          discovered: 1,
          format: "netscape_html",
          imported: 1,
          profiles: 1,
          skipped: 0,
          warnings: [],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["bookmark html"], "bookmarks.html", {
      type: "text/html",
    });

    await importBookmarkFile(file);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/imports/bookmarks-file",
      expect.objectContaining({
        body: file,
        headers: { "Content-Type": "text/html" },
        method: "POST",
      }),
    );
  });

  it("uploads bookmark JSON to the JSON import endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          discovered: 1,
          format: "link_hoarder_json",
          imported: 1,
          profiles: 1,
          skipped: 0,
          warnings: [],
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["[]"], "bookmarks.json", {
      type: "application/json",
    });

    await importBookmarkJson(file);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/imports/bookmarks-json",
      expect.objectContaining({
        body: file,
        headers: { "Content-Type": "application/json" },
        method: "POST",
      }),
    );
  });

  it("fetches one bookmark preview through the versioned endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          bookmark_id: 7,
          description: "Preview description.",
          image_url: null,
          site_name: "Example",
          title: "Preview Title",
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getBookmarkPreview(7);

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/bookmarks/7/preview", undefined);
  });

  it("returns the API detail when a request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Invalid key" }), { status: 401 }),
      ),
    );

    await expect(listBookmarks("", 10, 0)).rejects.toThrow("Invalid key");
  });

  it("sends the sort order through the versioned endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], limit: 10, offset: 0, total: 0 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listBookmarks("", 10, 0, "oldest");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/bookmarks?limit=10&offset=0&sort=oldest",
      undefined,
    );
  });

  it("omits the sort order when no sort applies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], limit: 10, offset: 0, total: 0 })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listBookmarks("", 10, 0);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/bookmarks?limit=10&offset=0",
      undefined,
    );
  });
});
