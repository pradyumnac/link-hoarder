const MONTH_MS = 30 * 24 * 60 * 60 * 1000;

const relativeFormat = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

/** Render a stored UTC timestamp as local date and time text. */
export function formatLocalDateTime(value: string): string {
  return new Date(Date.parse(value)).toLocaleString();
}

/**
 * Render a stored UTC timestamp moment-style: relative time when the
 * bookmark is newer than a month, otherwise the local calendar date.
 */
export function formatBookmarkDate(value: string, now: number = Date.now()): string {
  const time = Date.parse(value);
  if (Number.isNaN(time)) {
    return value;
  }
  const elapsed = now - time;
  if (elapsed < 0 || elapsed >= MONTH_MS) {
    return new Date(time).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }
  const seconds = Math.round(elapsed / 1000);
  if (seconds < 60) {
    return relativeFormat.format(-seconds, "second");
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return relativeFormat.format(-minutes, "minute");
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return relativeFormat.format(-hours, "hour");
  }
  const days = Math.round(hours / 24);
  if (days < 7) {
    return relativeFormat.format(-days, "day");
  }
  return relativeFormat.format(-Math.round(days / 7), "week");
}
