import SuperlativeCard from "./SuperlativeCard";
import {
  AWARDS,
  filterHref,
  podiumRows,
  type SuperlativeFilters,
  type SuperlativeRow,
} from "@/lib/superlatives";

type Props = {
  rows: SuperlativeRow[];
  currentSeason: number;
  filters: SuperlativeFilters;
};

function seasonClass(active: boolean) {
  return `inline-flex min-h-9 items-center rounded border border-white/70 px-3 text-sm whitespace-nowrap transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
    active
      ? "bg-white font-semibold text-black"
      : "bg-transparent text-white hover:bg-white/10"
  }`;
}

function FilterToggle({
  name,
  label,
  checked,
}: {
  name: string;
  label: string;
  checked: boolean;
}) {
  return (
    <button
      type="submit"
      name={name}
      value={checked ? "0" : "1"}
      aria-pressed={checked}
      className="flex min-h-9 items-center gap-2 text-sm text-white"
    >
      <span
        aria-hidden
        className={`grid h-4 w-4 place-items-center rounded border text-[10px] leading-none ${
          checked
            ? "border-white bg-white font-bold text-black"
            : "border-white/70 bg-transparent"
        }`}
      >
        {checked ? "✓" : ""}
      </span>
      {label}
    </button>
  );
}

export default function SuperlativesView({
  rows,
  currentSeason,
  filters,
}: Props) {
  const scopeId = filters.scope === "all_time" ? "all_time" : String(currentSeason);
  const advancedOpen =
    !filters.players || !filters.teams || !filters.hideDefense;

  const visible = AWARDS.filter((award) =>
    award.group === "player" ? filters.players : filters.teams,
  )
    .map((award) => ({
      award,
      places: podiumRows(
        rows.filter((row) => row.category === award.id && row.scope === scopeId),
        filters.hideDefense,
        10,
      ),
    }))
    .filter((card) => card.places.length > 0);

  const prizesMissing = visible.some((card) =>
    card.places.some((row) => row.detail.prizes_missing),
  );

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Season window">
          <a
            href={filterHref(filters, { scope: "all_time" })}
            aria-current={filters.scope === "all_time" ? "page" : undefined}
            className={seasonClass(filters.scope === "all_time")}
          >
            All-Time
          </a>
          <a
            href={filterHref(filters, { scope: "season" })}
            aria-current={filters.scope === "season" ? "page" : undefined}
            className={seasonClass(filters.scope === "season")}
          >
            Current Season
          </a>
        </div>

        <details className="max-w-xl" open={advancedOpen || undefined}>
          <summary className="min-h-9 cursor-pointer text-sm text-white/80 underline decoration-white/30 underline-offset-2">
            Advanced filters
          </summary>
          <form action="/superlatives" method="get">
            <input type="hidden" name="scope" value={filters.scope} />
            <input type="hidden" name="players" value={filters.players ? "1" : "0"} />
            <input type="hidden" name="teams" value={filters.teams ? "1" : "0"} />
            <input type="hidden" name="dst" value={filters.hideDefense ? "1" : "0"} />
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
              <FilterToggle name="teams" label="Team Awards" checked={filters.teams} />
              <FilterToggle name="players" label="Player Awards" checked={filters.players} />
              <FilterToggle name="dst" label="Hide D/ST" checked={filters.hideDefense} />
            </div>
          </form>
        </details>
      </div>

      {prizesMissing ? (
        <p className="text-sm text-white/65">
          2022 and 2023 champion and runner-up amounts are still blank in the
          payouts file, so those season prizes are not included yet.
        </p>
      ) : null}

      {!rows.length ? (
        <p className="text-sm text-white/65">
          No superlatives yet. Apply the Supabase migration, then run{" "}
          <span className="font-mono text-white/80">python scrapers/superlatives.py --full</span>.
        </p>
      ) : !filters.players && !filters.teams ? (
        <p className="text-sm text-white/65">
          Turn on Player Awards, Team Awards, or both.
        </p>
      ) : !visible.length ? (
        <p className="text-sm text-white/65">
          Nothing in this window yet. {currentSeason} fills in as weeks finish.
        </p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {visible.map(({ award, places }) => (
            <SuperlativeCard key={award.id} award={award} places={places} />
          ))}
        </ul>
      )}
    </div>
  );
}
