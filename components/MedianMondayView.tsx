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
