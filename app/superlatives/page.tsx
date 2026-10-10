import type { Metadata } from "next";
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
    <div>
      <h1 className="text-2xl md:text-3xl font-bold">Superlatives</h1>
      <p className="mt-2 text-sm text-white/65">{formatReportStamp(report)}</p>
      <details className="mt-3 max-w-2xl md:hidden">
        <summary className="min-h-11 cursor-pointer text-sm text-white/70 underline decoration-white/40 underline-offset-2">
          How Superlatives works
        </summary>
        <p className="mt-2 text-sm text-white/70">
          All-Time covers 2022 through this season. Current Season is{" "}
          {currentSeason} only. Consolation weeks are ignored.
        </p>
      </details>
      <p className="mt-3 hidden max-w-2xl text-sm text-white/70 md:block">
        All-Time covers 2022 through this season. Current Season is{" "}
        {currentSeason} only. Consolation weeks are ignored.
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
