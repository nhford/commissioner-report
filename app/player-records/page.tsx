import type { Metadata } from "next";
import PlayerRecordsTable from "@/components/PlayerRecordsTable";
import { getPlayerRecords } from "@/lib/data";
import { formatReportStamp } from "@/lib/format";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "Player Records · Commissioner's Report",
  description:
    "Career fantasy win-loss for every player rostered in this league.",
};

export default async function PlayerRecordsPage() {
  const { report, players } = await getPlayerRecords();

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold">Player Records</h1>
      <p className="mt-2 text-sm text-white/65">{formatReportStamp(report)}</p>
      <p className="mt-3 max-w-2xl text-sm text-white/70">
        Regular-season and winners-bracket playoff games are counted separately.
        Consolation games do not count toward records, year-by-year starts, or
        average starter points. On-team W–L includes bench and IR; starter W–L
        is the starting lineup only. A title is credited if the player appeared
        on the champion&apos;s roster in any week that season.
        Filter by name, position, or minimum starts. Click a row for year-by-year
        fantasy teams, NFL clubs, and average points as a starter.
      </p>

      <div className="mt-6">
        <PlayerRecordsTable players={players} />
      </div>
    </div>
  );
}
