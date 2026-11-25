import type { Metadata } from "next";
import PlayerRecordsTable from "@/components/PlayerRecordsTable";
import ReportPage from "@/components/ReportPage";
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
    <ReportPage
      title="Player Records"
      updated={formatReportStamp(report)}
      how="Regular-season and winners-bracket playoff games are counted separately. Consolation games do not count toward records, year-by-year starts, or average starter points. On-team W–L includes bench and IR; starter W–L is the starting lineup only. A title is credited if the player appeared on the champion's roster in any week that season. Filter by name, position, or minimum starts. Click a row for year-by-year fantasy teams, NFL clubs, and average points as a starter."
    >
      <PlayerRecordsTable players={players} />
    </ReportPage>
  );
}
