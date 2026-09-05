"use client";

import { useMemo, useState } from "react";
import InPageTabs from "./InPageTabs";
import ReportTable, { type Column } from "./ReportTable";
import TradeChord from "./TradeChord";
import { activeOwners, allOwners } from "@/lib/owners";
import {
  chordMatrix,
  countPairs,
  ownersInPairs,
  type TradePair,
  type TradeRow,
} from "@/lib/trades";

type View = "active" | "all";

const COLUMNS: Column<TradePair>[] = [
  {
    key: "a",
    label: "Owner",
    natural: "asc",
    align: "left",
    sortValue: (row) => row.a,
    render: (row) => row.a,
  },
  {
    key: "b",
    label: "Owner",
    natural: "asc",
    align: "left",
    sortValue: (row) => row.b,
    render: (row) => row.b,
  },
  {
    key: "count",
    label: "Trades",
    natural: "desc",
    numeric: true,
    sortValue: (row) => row.count,
    render: (row) => row.count,
  },
];

export default function TradeOgamiView({ trades }: { trades: TradeRow[] }) {
  const [view, setView] = useState<View>("active");

  const { owners, pairs, matrix } = useMemo(() => {
    const pool = view === "active" ? activeOwners() : allOwners();
    const nextPairs = countPairs(trades, new Set(pool));
    const nextOwners = ownersInPairs(nextPairs);
    return {
      owners: nextOwners,
      pairs: nextPairs,
      matrix: chordMatrix(nextOwners, nextPairs),
    };
  }, [trades, view]);

  if (!trades.length) {
    return (
      <p className="text-sm text-white/65">
        No trades yet. Run{" "}
        <code className="text-white/80">python scrapers/trades.py</code> after
        applying the Supabase migration.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <InPageTabs
        label="Trade-o-gami owner set"
        value={view}
        onChange={setView}
        tabs={[
          { id: "active", label: "Active owners" },
          { id: "all", label: "All historical" },
        ]}
      />
      <p className="text-sm text-white/55">
        {view === "active"
          ? "Current-season owners only. Trades that involved a departed owner are hidden."
          : "Every owner who has ever been in the league, including Jack, Kyler, and Andoni."}{" "}
        {pairs.length
          ? `${pairs.reduce((sum, pair) => sum + pair.count, 0)} pair-counts across ${owners.length} owners.`
          : "No qualifying trades in this view."}
      </p>
      <div className="rounded-lg bg-white text-black">
        <TradeChord owners={owners} matrix={matrix} />
      </div>
      {pairs.length ? (
        <ReportTable
          caption="Completed trades between owner pairs"
          tableClassName="min-w-[20rem]"
          columns={COLUMNS}
          rows={pairs}
          rowKey={(row) => `${row.a}-${row.b}`}
          defaultSort={{ key: "count", dir: "desc" }}
        />
      ) : null}
    </div>
  );
}
