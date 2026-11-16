import type { Metadata } from "next";
import TradeOgamiView from "@/components/TradeOgamiView";
import { getTeamWeekSides, getTrades } from "@/lib/data";
import { formatReportStamp } from "@/lib/format";
import { pairGames } from "@/lib/ogami";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "O-Gami · Commissioner's Report",
  description:
    "A grid of trades, head-to-head records, and playoff meetings between fantasy owners.",
};

export default async function TradeOgamiPage() {
  const [{ report, trades }, weeks] = await Promise.all([
    getTrades(),
    getTeamWeekSides(),
  ]);

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold">O-Gami</h1>
      <p className="mt-2 text-sm text-white/65">{formatReportStamp(report)}</p>
      <p className="mt-3 max-w-2xl text-sm text-white/70">
        Each square is whether something happened between two owners. Trades
        and playoff games show the same count in both directions, so you can
        read a row or a column. Head-to-head is the row owner&apos;s record
        against the column owner. A dark square means it has not happened.
        Only completed trades count. Trades can also switch to a spool of the
        same pairs. Playoff Match is winners-bracket games only.
      </p>

      <div className="mt-6">
        <TradeOgamiView trades={trades} games={pairGames(weeks)} />
      </div>
    </div>
  );
}
