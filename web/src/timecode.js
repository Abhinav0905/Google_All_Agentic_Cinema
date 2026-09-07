export function msToTimecode(ms) {
  const safe = Math.max(0, Math.round(ms || 0));
  const h = Math.floor(safe / 3_600_000);
  const m = Math.floor((safe % 3_600_000) / 60_000);
  const s = Math.floor((safe % 60_000) / 1000);
  const milli = safe % 1000;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(milli).padStart(3, "0")}`;
}

export function seekSeconds(startMs) {
  return Math.max(0, (startMs - 1000) / 1000);
}
