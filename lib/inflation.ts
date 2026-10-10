import type { SuperlativeRow } from "./superlatives";

/**
 * BLS CPI-U, all items, U.S. city average, not seasonally adjusted (CUUR0000SA0).
 * October 2025 was not published; that month is the midpoint of September and November.
 * The latest index is August 2026.
 */
const CPI: Record<string, number> = {
  "2022-09": 296.808,
  "2022-10": 298.012,
  "2022-11": 297.711,
  "2022-12": 296.797,
  "2023-01": 299.17,
  "2023-02": 300.84,
  "2023-03": 301.836,
  "2023-04": 303.363,
  "2023-05": 304.127,
  "2023-06": 305.109,
  "2023-07": 305.691,
  "2023-08": 307.026,
  "2023-09": 307.789,
  "2023-10": 307.671,
  "2023-11": 307.051,
  "2023-12": 306.746,
  "2024-01": 308.417,
  "2024-02": 310.326,
  "2024-03": 312.332,
  "2024-04": 313.548,
  "2024-05": 314.069,
  "2024-06": 314.175,
  "2024-07": 314.54,
  "2024-08": 314.796,
  "2024-09": 315.301,
  "2024-10": 315.664,
  "2024-11": 315.493,
  "2024-12": 315.605,
  "2025-01": 317.671,
  "2025-02": 319.082,
  "2025-03": 319.799,
  "2025-04": 320.795,
  "2025-05": 321.465,
  "2025-06": 322.561,
  "2025-07": 323.048,
  "2025-08": 323.976,
  "2025-09": 324.8,
  "2025-10": 324.461,
  "2025-11": 324.122,
  "2025-12": 324.054,
  "2026-01": 325.252,
  "2026-02": 326.785,
  "2026-03": 330.213,
  "2026-04": 333.02,
  "2026-05": 335.123,
  "2026-06": 333.952,
  "2026-07": 333.918,
  "2026-08": 334.98,
};

const LATEST_KEY = "2026-08";
const LATEST = CPI[LATEST_KEY];

/** Thursday that opens week 1. The payout month is the Sunday of that week. */
const WEEK1_THURSDAY: Record<number, [number, number, number]> = {
  2022: [2022, 9, 8],
  2023: [2023, 9, 7],
  2024: [2024, 9, 5],
  2025: [2025, 9, 4],
  2026: [2026, 9, 10],
};

const DAY = 86_400_000;

export function payoutMonth(season: number, week: number) {
  const start = WEEK1_THURSDAY[season];
  if (!start) return { year: season, month: 12 };
  const thursday = Date.UTC(start[0], start[1] - 1, start[2]);
  const sunday = thursday + ((week - 1) * 7 + 3) * DAY;
  const date = new Date(sunday);
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1 };
}

function monthKey(year: number, month: number) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function indexFor(year: number, month: number) {
  const key = monthKey(year, month);
  if (CPI[key] != null) return CPI[key];
  if (key > LATEST_KEY) return LATEST;
  let y = year;
  let m = month;
  for (let step = 0; step < 24; step += 1) {
    m -= 1;
    if (m < 1) {
      m = 12;
      y -= 1;
    }
    const earlier = CPI[monthKey(y, m)];
    if (earlier != null) return earlier;
  }
  return LATEST;
}

/** Past dollars in August 2026 dollars. Weeks after the latest CPI stay nominal. */
export function inflateAmount(amount: number, season: number, week: number) {
  const { year, month } = payoutMonth(season, week);
  return amount * (LATEST / indexFor(year, month));
}

export function dollarText(amount: number) {
  return `$${Math.round(amount).toLocaleString("en-US")}`;
}

function earliest(place: SuperlativeRow) {
  let season = 9999;
  let week = 99;
  for (const payment of place.detail.payments ?? []) {
    if (payment.season < season || (payment.season === season && payment.week < week)) {
      season = payment.season;
      week = payment.week;
    }
  }
  return [season, week] as const;
}

function isOwner(place: { subject_key: string; subject_name: string }, owner: string) {
  return place.subject_name === owner || place.subject_key === owner;
}

function withExtras(places: SuperlativeRow[]) {
  const leader = places[0];
  const extras = (leader?.detail.alternates ?? []).map((alt, index) => ({
    category: leader.category,
    scope: leader.scope,
    rank: places.length + index + 1,
    subject_type: alt.subject_type,
    subject_key: String(alt.subject_key),
    subject_name: alt.subject_name,
    value: Number(alt.value),
    display: alt.display,
    detail: alt.detail ?? {},
  }));
  return [...places, ...extras];
}

function withoutOwner(places: SuperlativeRow[], owner: string | null) {
  if (!owner) return places;
  return places.filter((place) => !isOwner(place, owner));
}

/** Nominal top 10, optionally dropping one owner and moving the next owners up. */
export function nominalEarnings(places: SuperlativeRow[], hideOwner: string | null = null) {
  if (!hideOwner) return places.slice(0, 10);
  return withoutOwner(withExtras(places), hideOwner)
    .slice(0, 10)
    .map((row, index) => {
      const { alternates: _alternates, ...detail } = row.detail;
      return { ...row, rank: index + 1, detail };
    });
}

export function inflationRanked(places: SuperlativeRow[], hideOwner: string | null = null) {
  const leader = places[0];
  if (!leader?.detail.payments?.length) return nominalEarnings(places, hideOwner);
  const ranked = withoutOwner(withExtras(places), hideOwner).map((place) => {
    const exact = new Map<string, number>();
    for (const payment of place.detail.payments ?? []) {
      const adjusted = inflateAmount(payment.amount, payment.season, payment.week);
      exact.set(payment.label, (exact.get(payment.label) ?? 0) + adjusted);
    }
    const lines = (place.detail.lines ?? []).map((line) => ({
      label: line.label,
      amount: Math.round(exact.get(line.label) ?? line.amount),
    }));
    const total = lines.reduce((sum, line) => sum + line.amount, 0);
    const { alternates: _alternates, ...detail } = place.detail;
    return {
      ...place,
      value: total,
      display: dollarText(total),
      detail: { ...detail, lines },
    };
  });
  ranked.sort((left, right) => {
    if (right.value !== left.value) return right.value - left.value;
    const [leftSeason, leftWeek] = earliest(left);
    const [rightSeason, rightWeek] = earliest(right);
    if (leftSeason !== rightSeason) return leftSeason - rightSeason;
    if (leftWeek !== rightWeek) return leftWeek - rightWeek;
    return left.subject_name.localeCompare(right.subject_name);
  });
  return ranked.slice(0, 10).map((row, index) => ({ ...row, rank: index + 1 }));
}

export function earningsBoard(places: SuperlativeRow[], adjust: boolean, hideKeshav: boolean) {
  const hidden = hideKeshav ? "Keshav" : null;
  return adjust ? inflationRanked(places, hidden) : nominalEarnings(places, hidden);
}
