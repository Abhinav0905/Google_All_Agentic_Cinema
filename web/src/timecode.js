/** Format milliseconds as an SRT-style timecode: HH:MM:SS,mmm */
export function msToTimecode(ms) {
  const safe = Math.max(0, Math.round(Number(ms) || 0));
  const h = Math.floor(safe / 3_600_000);
  const m = Math.floor((safe % 3_600_000) / 60_000);
  const s = Math.floor((safe % 60_000) / 1000);
  const milli = safe % 1000;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(milli).padStart(3, "0")}`;
}

/** Inclusive range used in the finding drawer and fix diffs. */
export function msToRange(startMs, endMs) {
  return `${msToTimecode(startMs)} → ${msToTimecode(endMs)}`;
}

/** Seek the picture 1 second before the finding, never before zero. */
export function seekSeconds(startMs) {
  return Math.max(0, (startMs - 1000) / 1000);
}

/** UTC wall clock for history rows. */
export function formatStamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}
