"use client";

import { useMemo, useState } from "react";
import ReportTable, { type Column, type SortDir } from "./ReportTable";
import TeamLogo from "./TeamLogo";
import type { MedianStanding } from "@/lib/data";
import { formatPct, formatPayout } from "@/lib/format";
import { logoPublicUrl } from "@/lib/logos";

type SortKey = "team" | "current" | "projection" | "median" | "payout";

const SORTS: { key: SortKey; label: string; natural: SortDir }[] = [
  { key: "current", label: "Score", natural: "desc" },
  { key: "projection", label: "Proj", natural: "desc" },
  { key: "median", label: "Median %", natural: "desc" },
  { key: "payout", label: "Payout", natural: "desc" },
];

function valueFor(row: MedianStanding, key: SortKey) {
  if (key === "team") return row.team;
  return Number(row[key]);
}

const COLUMNS: Column<MedianStanding>[] = [
  {
    key: "team",
    label: "Team",
    natural: "desc",
    align: "left",
    sortValue: (row) => row.team,
    render: (row) => (
      <span className="flex min-w-0 items-center gap-2">
        <TeamLogo src={logoPublicUrl(row.logo_path)} alt={row.team} />
        <span className="truncate font-semibold">{row.team}</span>
      </span>
    ),
  },
  {
    key: "current",
    label: "Score",
    natural: "desc",
    numeric: true,
    sortValue: (row) => row.current,
    render: (row) => Number(row.current).toFixed(2),
  },
  {
    key: "projection",
    label: "Proj",
    natural: "desc",
    numeric: true,
    sortValue: (row) => row.projection,
    render: (row) => Number(row.projection).toFixed(2),
  },
  {
    key: "median",
    label: "Median %",
    natural: "desc",
    numeric: true,
    sortValue: (row) => row.median,
    render: (row) => formatPct(Number(row.median)),
  },
  {
    key: "payout",
    label: "Payout",
    natural: "desc",
    numeric: true,
    sortValue: (row) => row.payout,
    render: (row) => formatPayout(Number(row.payout)),
  },
];

type Props = {
  rows: MedianStanding[];
};

export default function MedianStandings({ rows }: Props) {
  const cutoff = Math.floor(rows.length / 2);
  const [sorted, setSorted] = useState<{ key: SortKey; dir: SortDir }>({
    key: "current",
    dir: "desc",
  });

  const data = useMemo(() => {
    const sign = sorted.dir === "asc" ? -1 : 1;
    return [...rows].sort((a, b) => {
      const av = valueFor(a, sorted.key);
      const bv = valueFor(b, sorted.key);
      if (av < bv) return sign;
      if (av > bv) return -sign;
      return 0;
    });
  }, [rows, sorted]);

  return (
    <>
      <div className="md:hidden space-y-3">
        <div
          className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1"
          role="group"
          aria-label="Sort standings"
        >
          {SORTS.map((sort) => {
            const active = sorted.key === sort.key;
            return (
              <button
                key={sort.key}
                type="button"
                aria-pressed={active}
                aria-label={
                  active
                    ? `Sorted by ${sort.label}, ${sorted.dir === "desc" ? "high to low" : "low to high"}`
                    : `Sort by ${sort.label}`
                }
                className={`min-h-11 shrink-0 px-3 text-sm whitespace-nowrap rounded border border-white/70 touch-manipulation transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
                  active
                    ? "bg-white text-black font-semibold"
                    : "bg-transparent text-white hover:bg-white/10"
                }`}
                onClick={() => {
                  const nextDir =
                    active && sorted.dir === sort.natural
                      ? sort.natural === "desc"
                        ? "asc"
                        : "desc"
                      : sort.natural;
                  setSorted({ key: sort.key, dir: nextDir });
                }}
              >
                {sort.label}
                {active ? (sorted.dir === "desc" ? " ↓" : " ↑") : ""}
              </button>
            );
          })}
        </div>

        <h2 className="sr-only">
          Fantasy football median standings by team score, median chance, and
          expected payout
        </h2>
        <ol className="space-y-2">
          {data.map((row) => {
            const above = row.rank <= cutoff;
            return (
              <li
                key={row.team}
                className={`rounded-lg px-3 py-3 text-black ${
                  above ? "bg-emerald-50" : "bg-white"
                }`}
              >
                <div className="flex items-start gap-3">
                  <TeamLogo
                    src={logoPublicUrl(row.logo_path)}
                    alt=""
                    size="sm"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold leading-snug">{row.team}</p>
                    {above ? (
                      <p className="mt-0.5 text-xs font-medium text-emerald-800">
                        Top half
                      </p>
                    ) : null}
                    <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <dt className="text-xs text-neutral-500">Score</dt>
                        <dd className="tabular-nums font-medium">
                          {Number(row.current).toFixed(2)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-neutral-500">Proj</dt>
                        <dd className="tabular-nums font-medium">
                          {Number(row.projection).toFixed(2)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-neutral-500">Payout</dt>
                        <dd className="tabular-nums font-medium">
                          {formatPayout(Number(row.payout))}
                        </dd>
                      </div>
                    </dl>
                  </div>
                  <div className="w-[4.75rem] shrink-0 text-right">
                    <p className="text-xs text-neutral-500">Median</p>
                    <p className="text-xl font-bold tabular-nums leading-tight">
                      {formatPct(Number(row.median))}
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="hidden md:block">
        <ReportTable
          caption="Fantasy football median standings by team score, median chance, and expected payout"
          columns={COLUMNS}
          rows={rows}
          rowKey={(row) => row.team}
          defaultSort={{ key: "current", dir: "desc" }}
          rowClassName={(row) => (row.rank <= cutoff ? "bg-emerald-50" : "")}
        />
      </div>
    </>
  );
}
