"use client";

import { useMemo, useState } from "react";
import InPageTabs from "./InPageTabs";
import { formatSamPoints, type SamSeasonView } from "@/lib/sam";

type Props = {
  seasons: SamSeasonView[];
};

const HOW =
  "Start/sit accuracy adds up what your starters scored, leaving the defense out, and divides by the best lineup still on the roster. A kicker counts in the points you scored and not in that best lineup. Weeks are added first, then divided. Expected record is the share of the other teams you outscored and the share that outscored you each regular-season week. A tie is neither a win nor a loss.";

function barCaption(row: SamSeasonView["accuracy"][number]) {
  const score = `${row.actualLabel} / ${row.optimalLabel}`;
  return row.percentLabel ? `${score} (${row.percentLabel})` : score;
}

type ChartSort = "points" | "efficiency" | "record";

const CHART_SORTS: { id: ChartSort; label: string }[] = [
  { id: "points", label: "Total points" },
  { id: "efficiency", label: "Efficiency" },
  { id: "record", label: "Record" },
];

function AccuracyChart({
  rows,
  records,
}: {
  rows: SamSeasonView["accuracy"];
  records: SamSeasonView["expected"];
}) {
  const [sort, setSort] = useState<ChartSort>("efficiency");
  const byTeam = useMemo(
    () => new Map(records.map((row) => [row.teamId, row])),
    [records],
  );
  const ordered = useMemo(() => {
    return [...rows].sort((a, b) => {
      if (sort === "points") {
        return b.actual - a.actual || a.teamName.localeCompare(b.teamName);
      }
      if (sort === "efficiency") {
        return b.ratio - a.ratio || a.teamName.localeCompare(b.teamName);
      }
      const left = byTeam.get(a.teamId);
      const right = byTeam.get(b.teamId);
      const wins = (right?.wins ?? -1) - (left?.wins ?? -1);
      if (wins !== 0) return wins;
      const losses = (left?.losses ?? 0) - (right?.losses ?? 0);
      if (losses !== 0) return losses;
      return a.teamName.localeCompare(b.teamName);
    });
  }, [byTeam, rows, sort]);
  const scale = Math.max(
    1,
    ...ordered.map((row) => Math.max(row.actual, row.optimal)),
  );

  return (
    <figure className="rounded-lg bg-white px-3 py-4 text-neutral-900 sm:px-5">
      <figcaption className="mb-3 text-center text-sm font-semibold">
        Overall Start/Sit Accuracy
      </figcaption>
      <div
        className="mb-4 flex flex-wrap justify-center gap-2"
        role="tablist"
        aria-label="Chart sort"
      >
        {CHART_SORTS.map((option) => {
          const active = option.id === sort;
          return (
            <button
              key={option.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`min-h-9 rounded border px-3 text-sm ${
                active
                  ? "border-[#1a237e] bg-[#1a237e] font-semibold text-white"
                  : "border-neutral-300 text-neutral-800 hover:bg-neutral-100"
              }`}
              onClick={() => setSort(option.id)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <ul className="space-y-1.5">
        {ordered.map((row) => {
          const optimalWidth = (row.optimal / scale) * 100;
          const actualWidth = (row.actual / scale) * 100;
          const caption = barCaption(row);
          const labelInside = actualWidth >= 46;
          return (
            <li
              key={row.teamId}
              className="grid grid-cols-1 items-center gap-1 sm:grid-cols-[11rem_1fr] sm:gap-3"
            >
              <p
                className="truncate text-sm sm:text-right"
                title={row.teamName}
              >
                {row.teamName}
              </p>
              <div
                className="relative h-7"
                role="img"
                aria-label={`${row.teamName}, ${caption}`}
              >
                <div
                  className="absolute inset-y-0 left-0 bg-sky-200"
                  style={{ width: `${optimalWidth}%` }}
                />
                <div
                  className="absolute inset-y-0 left-0 bg-[#1a237e]"
                  style={{ width: `${actualWidth}%` }}
                />
                <span
                  className={`pointer-events-none absolute top-1/2 -translate-y-1/2 whitespace-nowrap text-[11px] font-medium leading-none ${
                    labelInside ? "text-white" : "text-neutral-900"
                  }`}
                  style={
                    labelInside
                      ? { right: `calc(${100 - actualWidth}% + 0.4rem)` }
                      : { left: `calc(${actualWidth}% + 0.35rem)` }
                  }
                >
                  {caption}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-2 grid grid-cols-1 sm:grid-cols-[11rem_1fr] sm:gap-3">
        <span className="hidden sm:block" />
        <div className="flex items-center justify-between border-t border-neutral-300 pt-1 text-[11px] text-neutral-500">
          <span>0</span>
          <span>Fantasy Points</span>
          <span>{formatSamPoints(scale)}</span>
        </div>
      </div>
    </figure>
  );
}

function recordLabel(wins: number, losses: number) {
  return `${wins.toFixed(2)}–${losses.toFixed(2)}`;
}

type SortKey = "team" | "record" | number;
type SortDir = "asc" | "desc";

function ExpectedRecord({
  weeks,
  rows,
}: {
  weeks: number[];
  rows: SamSeasonView["expected"];
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({
    key: "record",
    dir: "desc",
  });

  function toggleSort(key: SortKey) {
    setSort((current) => {
      if (current.key === key) {
        return { key, dir: current.dir === "desc" ? "asc" : "desc" };
      }
      return { key, dir: key === "team" ? "asc" : "desc" };
    });
  }

  const sorted = useMemo(() => {
    const sign = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      if (sort.key === "team") return a.teamName.localeCompare(b.teamName) * sign;
      if (sort.key === "record") {
        if (a.wins !== b.wins) return (a.wins - b.wins) * sign;
        if (a.losses !== b.losses) return (b.losses - a.losses) * sign;
        return a.teamName.localeCompare(b.teamName);
      }
      const weekIndex = weeks.indexOf(sort.key);
      const left = weekIndex >= 0 ? a.weekly[weekIndex] : null;
      const right = weekIndex >= 0 ? b.weekly[weekIndex] : null;
      if (left == null && right == null) return a.teamName.localeCompare(b.teamName);
      if (left == null) return 1;
      if (right == null) return -1;
      if (left !== right) return (left - right) * sign;
      return a.teamName.localeCompare(b.teamName);
    });
  }, [rows, sort, weeks]);

  function headerLabel(key: SortKey) {
    if (sort.key !== key) return "";
    return sort.dir === "asc" ? " ↑" : " ↓";
  }

  return (
    <section>
      <h2 className="text-lg font-semibold">Expected record</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-max border-collapse text-sm">
          <thead>
            <tr className="border-b border-white/15 text-left text-xs text-white/55">
              <th className="sticky left-0 bg-neutral-800 py-2 pr-4 font-medium" scope="col">
                <button
                  type="button"
                  className="min-h-11 text-left"
                  aria-sort={sort.key === "team" ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                  onClick={() => toggleSort("team")}
                >
                  Team{headerLabel("team")}
                </button>
              </th>
              <th className="py-2 pr-4 text-right font-medium" scope="col">
                <button
                  type="button"
                  className="min-h-11"
                  aria-sort={sort.key === "record" ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                  onClick={() => toggleSort("record")}
                >
                  Record{headerLabel("record")}
                </button>
              </th>
              {weeks.map((week) => (
                <th key={week} className="px-2 py-2 text-right font-medium" scope="col">
                  <button
                    type="button"
                    className="min-h-11 tabular-nums"
                    aria-sort={
                      sort.key === week
                        ? sort.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                    onClick={() => toggleSort(week)}
                  >
                    Wk {week}
                    {headerLabel(week)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.teamId} className="border-b border-white/10">
                <th
                  className="sticky left-0 bg-neutral-800 py-2 pr-4 text-left font-normal"
                  scope="row"
                >
                  {row.teamName}
                </th>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {recordLabel(row.wins, row.losses)}
                </td>
                {row.weekly.map((value, index) => (
                  <td
                    key={weeks[index]}
                    className="px-2 py-2 text-right tabular-nums text-white/85"
                  >
                    {value == null ? "—" : value.toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function SamsStuff({ seasons }: Props) {
  const [seasonId, setSeasonId] = useState(String(seasons[0]?.season ?? ""));
  const view = useMemo(
    () => seasons.find((season) => String(season.season) === seasonId) ?? seasons[0],
    [seasonId, seasons],
  );

  if (!seasons.length || !view) {
    return (
      <p className="text-sm text-white/65">
        No regular-season weeks stored yet.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <InPageTabs
        label="Season"
        value={String(view.season)}
        onChange={setSeasonId}
        tabs={seasons.map((season) => ({
          id: String(season.season),
          label: String(season.season),
        }))}
      />

      {view.accuracy.length ? (
        <AccuracyChart rows={view.accuracy} records={view.expected} />
      ) : (
        <p className="text-sm text-white/65">
          No lineup rows for {view.season}.
        </p>
      )}

      {view.expected.length ? (
        <ExpectedRecord key={view.season} weeks={view.weeks} rows={view.expected} />
      ) : (
        <p className="text-sm text-white/65">No scores for {view.season}.</p>
      )}
    </div>
  );
}

export { HOW as SAM_HOW };
