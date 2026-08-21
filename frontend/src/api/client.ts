import type { components } from "./schema";

export type Bookmark = components["schemas"]["BookmarkRead"];
export type BookmarkCreate = components["schemas"]["BookmarkCreate"];
export type BookmarkPage = components["schemas"]["BookmarkPage"];
export type BookmarkUpdate = components["schemas"]["BookmarkUpdate"];
export type Browser = components["schemas"]["Browser"];
export type ImportResult = components["schemas"]["ImportResult"];

const API_PREFIX = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, init);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(payload?.detail ?? `Request failed with HTTP ${response.status}.`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function listBookmarks(
  query: string,
  limit: number,
  offset: number,
): Promise<BookmarkPage> {
  const parameters = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (query) {
    parameters.set("query", query);
  }
  return request<BookmarkPage>(`/bookmarks?${parameters.toString()}`);
}

export function createBookmark(bookmark: BookmarkCreate): Promise<Bookmark> {
  return request<Bookmark>("/bookmarks", {
    body: JSON.stringify(bookmark),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export function updateBookmark(
  bookmarkId: number,
  bookmark: BookmarkUpdate,
): Promise<Bookmark> {
  return request<Bookmark>(`/bookmarks/${bookmarkId}`, {
    body: JSON.stringify(bookmark),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
}

export function deleteBookmark(bookmarkId: number): Promise<void> {
  return request<void>(`/bookmarks/${bookmarkId}`, { method: "DELETE" });
}

export function importBrowserFile(
  browser: Browser,
  file: File,
): Promise<ImportResult> {
  const parameters = new URLSearchParams({ browser });
  return request<ImportResult>(`/imports/browser-file?${parameters.toString()}`, {
    body: file,
    headers: { "Content-Type": "application/octet-stream" },
    method: "POST",
  });
}
