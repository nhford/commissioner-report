export const TOP_SCORER_PAYOUT = 75;

export function formatPct(value: number) {
  return `${(Math.round(value * 1000) / 10).toFixed(1)}%`;
}

export function formatPayout(value: number, payout = TOP_SCORER_PAYOUT) {
  return `$${(Math.round(value * payout * 100) / 100).toFixed(2)}`;
}

export function formatRecord(wins: number, games: number) {
  return `${wins}–${Math.max(0, games - wins)}`;
}

export function formatPullLabel(week: number, pulledAt: string) {
  const date = new Date(pulledAt);
  if (Number.isNaN(date.getTime())) return `Week ${week}`;
  const weekday = date.toLocaleDateString("en-US", { weekday: "short" });
  const month = date.toLocaleDateString("en-US", { month: "short" });
  const day = date.getDate();
  const time = date
    .toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    })
    .replace(" ", "")
    .toLowerCase();
  return `Week ${week} · ${weekday} ${month} ${day} ${time}`;
}

export function formatUpdated(iso: string | null | undefined) {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatThrough(
  season: number | null | undefined,
  week: number | null | undefined,
) {
  if (season == null) return null;
  if (week != null) return `through ${season} week ${week}`;
  return `through ${season}`;
}

export function formatReportStamp(
  report: {
    last_updated?: string | null;
    through_season?: number | null;
    through_week?: number | null;
  } | null,
  empty = "No scrape yet.",
) {
  const through = formatThrough(report?.through_season, report?.through_week);
  const updated = formatUpdated(report?.last_updated);
  const parts = [
    ...(through ? [through] : []),
    ...(updated ? [`Last updated ${updated}`] : []),
  ];
  return parts.length ? `${parts.join(". ")}.` : empty;
}
