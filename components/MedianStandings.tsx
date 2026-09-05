"use client";

import ReportTable, { type Column } from "./ReportTable";
import TeamLogo from "./TeamLogo";
import type { MedianStanding } from "@/lib/data";
import { formatPct, formatPayout } from "@/lib/format";
import { logoPublicUrl } from "@/lib/logos";

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

  return (
    <ReportTable
      caption="Fantasy football median standings by team score, median chance, and expected payout"
      columns={COLUMNS}
      rows={rows}
      rowKey={(row) => row.team}
      defaultSort={{ key: "current", dir: "desc" }}
      rowClassName={(row) => (row.rank <= cutoff ? "bg-emerald-50" : "")}
    />
  );
}
