import { afterEach, describe, expect, it, vi } from "vitest";

import { importBookmarkFile, listBookmarks } from "../src/api/client";

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

  it("returns the API detail when a request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Invalid key" }), { status: 401 }),
      ),
    );

    await expect(listBookmarks("", 10, 0)).rejects.toThrow("Invalid key");
  });
});
