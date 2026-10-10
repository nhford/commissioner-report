import { allOwners } from "@/lib/owners";
import SuperlativeCard from "./SuperlativeCard";
import {
  AWARDS,
  FIRST_SEASON,
  HIDDEN_ON_OWNER,
  TILE_FILTERS,
  boardAsOf,
  boardChangedAt,
  duoTradeRows,
  filterHref,
  leastTeamRows,
  podiumRows,
  scopeKey,
  starterRows,
  tileApplies,
  tileEmptiesLocally,
  type DepartedPlace,
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
  const scopeId = scopeKey(filters.fromYear, filters.toYear, filters.owner);
  const allTime = filters.fromYear === FIRST_SEASON && filters.toYear === currentSeason;
  const currentOnly = filters.fromYear === currentSeason && filters.toYear === currentSeason;
  const ajayFilter = TILE_FILTERS.find((filter) => filter.param === "ajay");
  const advancedOpen =
    !allTime ||
    !filters.players ||
    !filters.teams ||
    !filters.hideDefense ||
    !filters.sortLatest;
  const [asOfSeason, asOfWeek] = boardAsOf(rows);

  const years = Array.from(
    { length: currentSeason - FIRST_SEASON + 1 },
    (_, index) => FIRST_SEASON + index,
  );
  const yearSpan = Math.max(currentSeason - FIRST_SEASON, 1);
  const yearPct = (year: number) => ((year - FIRST_SEASON) / yearSpan) * 100;
  const visible = AWARDS.filter(
    (award) =>
      (award.group === "player" ? filters.players : filters.teams) &&
      !(filters.owner && HIDDEN_ON_OWNER.has(award.id)),
  )
    .map((award, index) => {
      const matching = rows.filter((row) => row.category === award.id && row.scope === scopeId);
      const storedLeader = matching.find((row) => row.rank === 1);
      const leaving: DepartedPlace[] =
        award.id === "least_fantasy_teams"
          ? (filters.hideDefense
              ? storedLeader?.detail.hide_departed
              : storedLeader?.detail.departed) ?? []
          : [];
      const places =
        award.id === "least_fantasy_teams"
          ? leastTeamRows(matching, Boolean(filters.tiles.inactive), currentSeason, 10)
          : award.id === "team_duo_trades"
            ? duoTradeRows(
                matching,
                Boolean(
                  ajayFilter &&
                    filters.tiles.ajay &&
                    tileApplies(ajayFilter, filters.owner) &&
                    !tileEmptiesLocally(ajayFilter, filters.owner),
                ),
                10,
              )
            : (award.id === "nfl_starter_week" ? starterRows : podiumRows)(
                matching,
                filters.hideDefense,
                10,
              );
      return {
        award,
        index,
        leaving,
        places,
      };
    })
    .filter((card) => card.places.length > 0);

  if (filters.sortLatest) {
    visible.sort((left, right) => {
      const a = boardChangedAt(left.places, filters.hideDefense);
      const b = boardChangedAt(right.places, filters.hideDefense);
      if (a[0] !== b[0]) return b[0] - a[0];
      if (a[1] !== b[1]) return b[1] - a[1];
      return left.index - right.index;
    });
  }

  const prizesMissing = visible.some((card) =>
    card.places.some((row) => row.detail.prizes_missing),
  );

  return (
    <div className="space-y-4">
      <form id="superlative-filters" action="/superlatives" method="get" className="space-y-2">
        <input type="hidden" name="players" value={filters.players ? "1" : "0"} />
        <input type="hidden" name="teams" value={filters.teams ? "1" : "0"} />
        <input type="hidden" name="dst" value={filters.hideDefense ? "1" : "0"} />
        <input type="hidden" name="latest" value={filters.sortLatest ? "1" : "0"} />
        {TILE_FILTERS.map((filter) => (
          <input
            key={filter.param}
            type="hidden"
            name={filter.param}
            value={filters.tiles[filter.param] ? "1" : "0"}
          />
        ))}
        <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-white/60">Team</span>
            <select
              name="owner"
              defaultValue={filters.owner ?? ""}
              className={`min-h-9 min-w-36 rounded border border-white/70 px-2 text-sm ${
                filters.owner
                  ? "bg-white font-semibold text-black"
                  : "bg-transparent text-white"
              }`}
            >
              <option value="">All owners</option>
              {allOwners().map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Season window">
            <a
              href={filterHref(filters, currentSeason, {
                fromYear: FIRST_SEASON,
                toYear: currentSeason,
              })}
              aria-current={allTime ? "page" : undefined}
              className={seasonClass(allTime)}
            >
              All-Time
            </a>
            <a
              href={filterHref(filters, currentSeason, {
                fromYear: currentSeason,
                toYear: currentSeason,
              })}
              aria-current={currentOnly ? "page" : undefined}
              className={seasonClass(currentOnly)}
            >
              Current Season
            </a>
          </div>
        </div>

        <details className="max-w-xl" open={advancedOpen || undefined}>
          <summary className="min-h-9 cursor-pointer text-sm text-white/80 underline decoration-white/30 underline-offset-2">
            Advanced filters
          </summary>
            <div className="year-scale mt-4">
              <p className="text-sm text-white/80">
                {filters.fromYear}–{filters.toYear}
              </p>
              <div className="year-axis">
                {years.map((year) => (
                  <span
                    key={year}
                    className={`year-label ${
                      year >= filters.fromYear && year <= filters.toYear
                        ? "is-selected"
                        : ""
                    }`}
                    style={{ left: `${yearPct(year)}%` }}
                  >
                    {year}
                  </span>
                ))}
                {years.map((year) => (
                  <span
                    key={`tick-${year}`}
                    className="year-tick"
                    style={{ left: `${yearPct(year)}%` }}
                  />
                ))}
                <div className="year-track" />
                <div
                  className="year-fill"
                  style={{
                    left: `${yearPct(filters.fromYear)}%`,
                    width: `${yearPct(filters.toYear) - yearPct(filters.fromYear)}%`,
                  }}
                />
                <div className="year-range">
                  <input
                    type="range"
                    name="from"
                    min={FIRST_SEASON}
                    max={currentSeason}
                    step={1}
                    defaultValue={filters.fromYear}
                    aria-label="From"
                  />
                  <input
                    type="range"
                    name="to"
                    min={FIRST_SEASON}
                    max={currentSeason}
                    step={1}
                    defaultValue={filters.toYear}
                    aria-label="To"
                  />
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
              <FilterToggle name="latest" label="Sort by Latest" checked={filters.sortLatest} />
              <FilterToggle name="teams" label="Team Awards" checked={filters.teams} />
              <FilterToggle name="players" label="Player Awards" checked={filters.players} />
              <FilterToggle name="dst" label="Hide D/ST" checked={filters.hideDefense} />
            </div>
        </details>
        <script
          dangerouslySetInnerHTML={{
            __html: `document.querySelectorAll("#superlative-filters input[type=range], #superlative-filters select").forEach(function (el) { el.addEventListener("change", function () { el.form.requestSubmit(); }); });`,
          }}
        />
        <style
          dangerouslySetInnerHTML={{
            __html: `.year-axis{position:relative;height:3.4rem;margin:0.35rem 0.625rem 0}.year-label{position:absolute;top:0;transform:translateX(-50%);font-size:0.75rem;line-height:1rem;color:rgba(255,255,255,0.4);white-space:nowrap}.year-label.is-selected{color:#fff;font-weight:600}.year-tick{position:absolute;top:1.15rem;width:1px;height:0.45rem;background:rgba(255,255,255,0.55);transform:translateX(-50%)}.year-track{position:absolute;top:2.05rem;left:0;right:0;height:4px;border-radius:999px;background:rgba(255,255,255,0.28)}.year-fill{position:absolute;top:2.05rem;height:4px;border-radius:999px;background:#fff}.year-range{position:absolute;top:1.15rem;left:0;right:0;height:2rem}.year-range input[type=range]{position:absolute;left:-0.625rem;width:calc(100% + 1.25rem);height:2rem;margin:0;background:transparent;pointer-events:none;appearance:none;-webkit-appearance:none}.year-range input[type=range]::-webkit-slider-runnable-track{height:4px;background:transparent}.year-range input[type=range]::-webkit-slider-thumb{pointer-events:auto;appearance:none;-webkit-appearance:none;height:1.25rem;width:1.25rem;margin-top:-0.5rem;border-radius:9999px;background:#fff;border:2px solid #111;cursor:pointer}.year-range input[type=range]::-moz-range-track{height:4px;background:transparent;border:0}.year-range input[type=range]::-moz-range-thumb{pointer-events:auto;height:1.25rem;width:1.25rem;border:2px solid #111;border-radius:9999px;background:#fff;cursor:pointer}`,
          }}
        />
      </form>

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
        <ul className="grid gap-3 min-[90rem]:grid-cols-2">
          {visible.map(({ award, places, leaving }) => (
            <SuperlativeCard
              key={award.id}
              award={award}
              places={places}
              hideDefense={filters.hideDefense}
              asOfSeason={asOfSeason}
              asOfWeek={asOfWeek}
              leaving={leaving}
              filters={filters}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
