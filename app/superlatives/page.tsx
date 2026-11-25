import type { Metadata } from "next";
import ReportPage from "@/components/ReportPage";
import SuperlativesView from "@/components/SuperlativesView";
import { getSuperlatives } from "@/lib/data";
import { formatReportStamp } from "@/lib/format";
import { readFilters, scopeKey } from "@/lib/superlatives";
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
    from?: string | string[];
    to?: string | string[];
    owner?: string | string[];
    players?: string | string[];
    teams?: string | string[];
    dst?: string | string[];
    latest?: string | string[];
    teamdst?: string | string[];
    consolation?: string | string[];
    inactive?: string | string[];
    ajay?: string | string[];
    keshav?: string | string[];
  }>;
}) {
  const currentSeason = league.current_season;
  const filters = readFilters(await searchParams, currentSeason);
  const { report, rows } = await getSuperlatives(
    scopeKey(filters.fromYear, filters.toYear, filters.owner),
  );

  return (
    <ReportPage
      title="Superlatives"
      updated={formatReportStamp(report)}
      how={`All-Time covers 2022 through this season. Current Season is ${currentSeason} only. Consolation weeks are ignored.`}
    >
      <SuperlativesView
        rows={rows}
        currentSeason={currentSeason}
        filters={filters}
      />
    </ReportPage>
  );
}
