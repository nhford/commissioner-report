import type { Metadata } from "next";
import MedianMondayView from "@/components/MedianMondayView";
import ReportPage from "@/components/ReportPage";
import { getMedianHistory, getReport } from "@/lib/data";
import { formatUpdated } from "@/lib/format";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Median Watch · Commissioner's Report",
  description:
    "Estimated chance each team finishes above the league median this week.",
};

export default async function MedianMondayPage() {
  const [{ pulls, standings }, report] = await Promise.all([
    getMedianHistory(),
    getReport("median-monday"),
  ]);
  const latest = pulls[0];

  const stamp = latest
    ? `Week ${latest.week}${latest.season ? ` · ${latest.season}` : ""}`
    : report?.current_week
      ? `Week ${report.current_week}`
      : "No pulls yet";
  const updated = report?.last_updated
    ? `${stamp}. Last updated ${formatUpdated(report.last_updated)}.`
    : `${stamp}.`;

  return (
    <ReportPage
      title="Median Watch"
      updated={updated}
      how="Each week a team can beat its opponent and also earn a bonus win for finishing in the top half of the league. These percentages are a Monte Carlo of remaining starter projections. Snapshots from here on store M1, the original gamma, and M2, the game simulation. Choose any pull to see that snapshot."
    >
      <MedianMondayView pulls={pulls} standings={standings} />
    </ReportPage>
  );
}
