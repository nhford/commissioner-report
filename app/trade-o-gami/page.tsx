import type { Metadata } from "next";
import TradeOgamiView from "@/components/TradeOgamiView";
import { getTrades } from "@/lib/data";
import { formatReportStamp } from "@/lib/format";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "Trade-o-gami · Commissioner's Report",
  description:
    "Chord diagram of completed trades between fantasy owners in this league.",
};

export default async function TradeOgamiPage() {
  const { report, trades } = await getTrades();

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold">Trade-o-gami</h1>
      <p className="mt-2 text-sm text-white/65">{formatReportStamp(report)}</p>
      <p className="mt-3 max-w-2xl text-sm text-white/70">
        Each ribbon is the number of completed trades between two owners. Arc
        length is how often that owner shows up in a deal. Proposed, vetoed, and
        canceled trades do not count. Switch to all historical to bring back
        departed owners.
      </p>

      <div className="mt-6">
        <TradeOgamiView trades={trades} />
      </div>
    </div>
  );
}
