"use client";

import { useMemo, useState } from "react";
import InPageTabs from "./InPageTabs";
import MedianStandings from "./MedianStandings";
import type { MedianPull, MedianStanding } from "@/lib/data";
import league from "@/data/league.json";
import { formatPullLabel } from "@/lib/format";

type Props = {
  pulls: MedianPull[];
  standings: MedianStanding[];
};

export default function MedianMondayView({ pulls, standings }: Props) {
  const [pullId, setPullId] = useState(pulls[0]?.id ?? "");

  const rows = useMemo(
    () => standings.filter((row) => row.pull_id === pullId),
    [pullId, standings],
  );

  const cutoff = Math.max(1, Math.floor(rows.length / 2));

  if (!pulls.length) {
    return (
      <p className="text-sm text-white/65">
        No Median Monday pulls yet. Run the scraper after applying the Supabase
        migration.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <label className="block md:hidden text-sm text-white/70">
        Snapshot
        <select
          value={pullId}
          onChange={(event) => setPullId(event.target.value)}
          className="mt-1 block w-full min-h-11 rounded border border-white/70 bg-neutral-800 px-3 text-white touch-manipulation focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        >
          {pulls.map((pull) => (
            <option key={pull.id} value={pull.id}>
              {formatPullLabel(
                pull.week,
                pull.pulled_at,
                pull.season,
                league.current_season,
              )}
            </option>
          ))}
        </select>
      </label>
      <div className="hidden md:block">
        <InPageTabs
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
