import type { Metadata } from "next";
import MedianMondayView from "@/components/MedianMondayView";
import { getMedianHistory, getReport } from "@/lib/data";
import { formatUpdated } from "@/lib/format";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Median Monday · Commissioner's Report",
  description:
    "Estimated chance each team finishes above the league median this week.",
};

export default async function MedianMondayPage() {
  const [{ pulls, standings }, report] = await Promise.all([
    getMedianHistory(),
    getReport("median-monday"),
  ]);
  const latest = pulls[0];

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold">Median Monday</h1>
      <p className="mt-2 text-sm text-white/65">
        {latest
          ? `Week ${latest.week}${latest.season ? ` · ${latest.season}` : ""}`
          : report?.current_week
            ? `Week ${report.current_week}`
            : "No pulls yet"}
        {report?.last_updated
          ? `. Last updated ${formatUpdated(report.last_updated)}.`
          : "."}
      </p>
      <p className="mt-3 max-w-2xl text-sm text-white/70">
        Each week a team can beat its opponent and also earn a bonus win for
        finishing in the top half of the league. These percentages are a Monte
        Carlo of remaining starter projections. Choose any pull to see that
        snapshot.
      </p>

      <div className="mt-6">
        <MedianMondayView pulls={pulls} standings={standings} />
      </div>
    </div>
  );
}
