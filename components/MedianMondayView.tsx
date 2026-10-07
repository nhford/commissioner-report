"use client";

import { useMemo, useState } from "react";
import InPageTabs from "./InPageTabs";
import MedianStandings from "./MedianStandings";
import type { MedianPull, MedianStanding } from "@/lib/data";
import league from "@/data/league.json";
import { formatPullLabel } from "@/lib/format";

type ModelId = "M1" | "M2";

type Props = {
  pulls: MedianPull[];
  standings: MedianStanding[];
};

function hasBothModels(rows: MedianStanding[]) {
  return (
    rows.length > 0 &&
    rows.every(
      (row) =>
        row.median_m1 != null &&
        row.payout_m1 != null &&
        row.median_m2 != null &&
        row.payout_m2 != null,
    )
  );
}

function rowsForModel(rows: MedianStanding[], model: ModelId, dual: boolean) {
  if (!dual) return rows;
  return rows.map((row) => ({
    ...row,
    median: Number(model === "M1" ? row.median_m1 : row.median_m2),
    payout: Number(model === "M1" ? row.payout_m1 : row.payout_m2),
  }));
}

export default function MedianMondayView({ pulls, standings }: Props) {
  const [pullId, setPullId] = useState(pulls[0]?.id ?? "");
  const [model, setModel] = useState<ModelId>("M2");

  const savedRows = useMemo(
    () => standings.filter((row) => row.pull_id === pullId),
    [pullId, standings],
  );
  const dual = hasBothModels(savedRows);
  const rows = useMemo(
    () => rowsForModel(savedRows, model, dual),
    [savedRows, model, dual],
  );

  const cutoff = Math.max(1, Math.floor(rows.length / 2));

  if (!pulls.length) {
    return (
      <p className="text-sm text-white/65">
        No Median Watch pulls yet. Run the scraper after applying the Supabase
        migration.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <InPageTabs
        scroll
        label="Pull"
        value={pullId}
        onChange={setPullId}
        tabs={pulls.map((pull) => ({
          id: pull.id,
          label: formatPullLabel(
            pull.week,
            pull.pulled_at,
            pull.season,
            league.current_season,
          ),
        }))}
      />
      <div
        className="flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Scoring model"
      >
        {(["M2", "M1"] as const).map((id) => {
          const active = dual && model === id;
          return (
            <button
              key={id}
              type="button"
              aria-pressed={active}
              disabled={!dual}
              className={`min-h-9 px-3 text-sm whitespace-nowrap rounded border border-white/70 transition-colors touch-manipulation focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
                !dual
                  ? "cursor-not-allowed bg-transparent text-white/35"
                  : active
                    ? "bg-white text-black font-semibold"
                    : "bg-transparent text-white hover:bg-white/10"
              }`}
              onClick={() => setModel(id)}
            >
              {id}
            </button>
          );
        })}
        <p className="text-xs text-white/55">
          {dual
            ? model === "M2"
              ? "M2 simulates the game, shares touchdowns, and can end a player's day mid-game."
              : "M1 is the original formula: an independent gamma for each remaining starter."
            : "This snapshot was saved with one model, so the M1 / M2 toggle is off."}
        </p>
      </div>
      <MedianStandings rows={rows} />
      <p className="text-xs text-white/55">
        <span className="md:hidden">Top half = currently above the median. </span>
        <span className="hidden md:inline">
          Emerald row = currently in the top {cutoff} (above median).{" "}
        </span>
        Payout is expected share of the weekly high-score prize.
      </p>
    </div>
  );
}
