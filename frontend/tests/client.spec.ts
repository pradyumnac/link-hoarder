import { afterEach, describe, expect, it, vi } from "vitest";

import { listBookmarks } from "../src/api/client";

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
