import { describe, expect, it } from "vitest";

import { formatBookmarkDate } from "../src/format";

const NOW = Date.parse("2026-10-06T12:00:00.000Z");
const iso = (ms: number): string => new Date(ms).toISOString();

describe("formatBookmarkDate", () => {
  /** Given a timestamp seconds old, the card shows a relative second count. */
  it("shows seconds-old bookmarks as relative time", () => {
    expect(formatBookmarkDate(iso(NOW - 30 * 1000), NOW)).toBe("30 seconds ago");
  });

  /** Given a timestamp minutes old, the card shows a relative minute count. */
  it("shows minutes-old bookmarks as relative time", () => {
    expect(formatBookmarkDate(iso(NOW - 5 * 60 * 1000), NOW)).toBe("5 minutes ago");
  });

  /** Given a timestamp hours old, the card shows a relative hour count. */
  it("shows hours-old bookmarks as relative time", () => {
    expect(formatBookmarkDate(iso(NOW - 3 * 60 * 60 * 1000), NOW)).toBe("3 hours ago");
  });

  /** Given a timestamp days old, the card shows a relative day count. */
  it("shows days-old bookmarks as relative time", () => {
    expect(formatBookmarkDate(iso(NOW - 6 * 24 * 60 * 60 * 1000), NOW)).toBe("6 days ago");
  });

  /** Given a timestamp weeks old but within a month, the card shows weeks. */
  it("shows weeks-old bookmarks as relative time", () => {
    expect(formatBookmarkDate(iso(NOW - 21 * 24 * 60 * 60 * 1000), NOW)).toBe("3 weeks ago");
  });

  /** Given a timestamp older than a month, the card shows the local date. */
  it("shows bookmarks older than a month as a calendar date", () => {
    const text = formatBookmarkDate(iso(NOW - 60 * 24 * 60 * 60 * 1000), NOW);

    expect(text).not.toContain("ago");
    expect(text).toMatch(/\d{4}/);
  });

  /** Given a future timestamp, the card falls back to the calendar date. */
  it("shows future timestamps as a calendar date", () => {
    const text = formatBookmarkDate(iso(NOW + 60 * 1000), NOW);

    expect(text).not.toContain("ago");
  });

  /** Given an unparsable value, the formatter returns it unchanged. */
  it("returns invalid timestamps unchanged", () => {
    expect(formatBookmarkDate("not-a-date", NOW)).toBe("not-a-date");
  });
});
