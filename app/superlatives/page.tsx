import type { Metadata } from "next";
import SuperlativesView from "@/components/SuperlativesView";
import { getSuperlatives } from "@/lib/data";
import { formatReportStamp } from "@/lib/format";
import { readFilters } from "@/lib/superlatives";
import league from "@/data/league.json";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "Superlatives · Commissioner's Report",
  description:
    "All-time and current-season fantasy superlatives for players and teams.",
};

export default async function SuperlativesPage({
  searchParams,
}: {
  searchParams: Promise<{
    scope?: string | string[];
    players?: string | string[];
    teams?: string | string[];
    dst?: string | string[];
  }>;
}) {
  const filters = readFilters(await searchParams);
  const { report, rows } = await getSuperlatives();
  const currentSeason = report?.season ?? league.current_season;

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold">Superlatives</h1>
      <p className="mt-2 text-sm text-white/65">{formatReportStamp(report)}</p>
      <details className="mt-3 max-w-2xl md:hidden">
        <summary className="min-h-11 cursor-pointer text-sm text-white/70 underline decoration-white/40 underline-offset-2">
          How Superlatives works
        </summary>
        <p className="mt-2 text-sm text-white/70">
          All-Time covers 2022 through this season. Current Season is {currentSeason}{" "}
          only. Weekly top-scorer pay is $50 in 2024 and $75 after that. Median
          streaks count regular-season weeks in the top 6 and can run from one
          season into the next. Consolation weeks are ignored.
        </p>
      </details>
      <p className="mt-3 hidden max-w-2xl text-sm text-white/70 md:block">
        All-Time covers 2022 through this season. Current Season is {currentSeason}{" "}
        only. Weekly top-scorer pay is $50 in 2024 and $75 after that. Median
        streaks count regular-season weeks in the top 6 and can run from one
        season into the next. Consolation weeks are ignored.
      </p>
      <div className="mt-6">
        <SuperlativesView
          rows={rows}
          currentSeason={currentSeason}
          filters={filters}
        />
      </div>
    </div>
  );
}
