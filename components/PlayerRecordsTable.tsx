"use client";

import { useMemo, useRef, useState, type ReactNode } from "react";
import InPageTabs from "./InPageTabs";
import ReportTable, { type Column } from "./ReportTable";
import TeamLogo from "./TeamLogo";
import { formatPct, formatRecord } from "@/lib/format";
import { nflLogoUrl } from "@/lib/logos";
import {
  DEFAULT_MIN_STARTS,
  SPECIAL_MIN_STARTS,
  filterPlayers,
  positionOptions,
  formatFantasyTeam,
  uniqueTeams,
  type PlayerRecord,
  type SpecialRecordFilter,
} from "@/lib/player-records";

function recordColumn(
  key: string,
  label: string,
  wins: (row: PlayerRecord) => number,
  games: (row: PlayerRecord) => number,
): Column<PlayerRecord> {
  return {
    key,
    label,
    natural: "desc",
    numeric: true,
    sortValue: (row) => wins(row),
    render: (row) => formatRecord(wins(row), games(row)),
  };
}

const COLUMNS: Column<PlayerRecord>[] = [
  {
    key: "name",
    label: "Player",
    natural: "desc",
    align: "left",
    sortValue: (row) => row.name,
    render: (row) => (
      <span className="block truncate font-semibold" title={row.name}>
        {row.name}
      </span>
    ),
  },
  {
    key: "pos",
    label: "Pos",
    natural: "desc",
    sortValue: (row) => row.pos,
    render: (row) => row.pos,
  },
  {
    key: "teams",
    label: "Teams",
    natural: "desc",
    sortValue: (row) => row.teams.join(","),
    render: (row) => {
      const teams = uniqueTeams(row.teams);
      return (
        <span className="flex flex-wrap items-center gap-1" title={teams.join(", ")}>
          {teams.map((team, index) => (
            <TeamLogo
              key={`${row.name}-${team}-${index}`}
              src={nflLogoUrl(team)}
              alt={team}
              size="sm"
            />
          ))}
        </span>
      );
    },
  },
  recordColumn("starterWl", "Starter", (row) => row.ws, (row) => row.gs),
  recordColumn("teamWl", "On team", (row) => row.w, (row) => row.g),
  recordColumn("playoffStarter", "Playoff (starter)", (row) => row.pws, (row) => row.pgs),
  recordColumn("playoffTeam", "Playoff (on team)", (row) => row.pw, (row) => row.pg),
  {
    key: "titles",
    label: "Titles",
    natural: "desc",
    numeric: true,
    sortValue: (row) => row.titles,
    render: (row) => row.titles,
  },
  {
    key: "winPct",
    label: "Win %",
    natural: "desc",
    numeric: true,
    sortValue: (row) => row.winPct,
    render: (row) => formatPct(row.winPct),
  },
];

type Props = {
  players: PlayerRecord[];
};

export default function PlayerRecordsTable({ players }: Props) {
  const [query, setQuery] = useState("");
  const [pos, setPos] = useState("All");
  const [minStarts, setMinStarts] = useState(DEFAULT_MIN_STARTS);
  const [special, setSpecial] = useState<SpecialRecordFilter>(null);
  const savedMinStarts = useRef<number | null>(null);
  const positions = useMemo(() => positionOptions(players), [players]);

  const rows = useMemo(
    () => filterPlayers(players, query, pos, minStarts, special),
    [minStarts, players, pos, query, special],
  );

  function toggleSpecial(next: Exclude<SpecialRecordFilter, null>) {
    const turningOff = special === next;
    if (turningOff) {
      setMinStarts(savedMinStarts.current ?? DEFAULT_MIN_STARTS);
      savedMinStarts.current = null;
      setSpecial(null);
      return;
    }
    if (special === null) savedMinStarts.current = minStarts;
    setMinStarts(SPECIAL_MIN_STARTS[next]);
    setSpecial(next);
  }

  if (!players.length) {
    return (
      <p className="text-sm text-white/65">
        No player records yet. Run{" "}
        <code className="text-white/80">python scrapers/player_records.py --full</code>{" "}
        after applying the Supabase migration.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <label className="block min-w-[12rem] flex-1 text-sm text-white/70">
          Search
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Player name"
            className="mt-1 block w-full min-h-9 rounded border border-white/70 bg-transparent px-3 text-white placeholder:text-white/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          />
        </label>
        <label className="block text-sm text-white/70">
          Min starts
          <input
            type="number"
            min={0}
            inputMode="numeric"
            value={minStarts}
            onChange={(event) => {
              const next = Number(event.target.value);
              setMinStarts(Number.isFinite(next) && next > 0 ? Math.floor(next) : 0);
            }}
            className="mt-1 block w-24 min-h-9 rounded border border-white/70 bg-transparent px-3 text-white tabular-nums focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          />
        </label>
      </div>
      <div className="space-y-3">
        <FilterRow label="Positions">
          <InPageTabs
            label="Positions"
            value={pos}
            onChange={setPos}
            tabs={positions.map((id) => ({ id, label: id }))}
          />
        </FilterRow>
        <FilterRow label="Other">
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Other">
            <Chip
              pressed={special === "undefeated"}
              onClick={() => toggleSpecial("undefeated")}
            >
              Undefeated
            </Chip>
            <Chip
              pressed={special === "winless"}
              onClick={() => toggleSpecial("winless")}
            >
              Winless
            </Chip>
          </div>
        </FilterRow>
      </div>
      <p className="text-sm text-white/55">
        {rows.length === players.length
          ? `${rows.length} players`
          : `${rows.length} of ${players.length} players`}
      </p>
      {rows.length ? (
        <ReportTable
          caption="Career fantasy win-loss for every player rostered in this league"
          tableClassName="min-w-[56rem]"
          columns={COLUMNS}
          rows={rows}
          rowKey={(row) => row.name}
          defaultSort={{ key: "starterWl", dir: "desc" }}
          renderExpanded={(row) => <SeasonDetail player={row} />}
        />
      ) : (
        <p className="text-sm text-white/65">No players match these filters.</p>
      )}
    </div>
  );
}

function FilterRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs uppercase tracking-wide text-white/50">{label}</p>
      {children}
    </div>
  );
}

function Chip({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`min-h-9 px-3 text-sm whitespace-nowrap rounded border border-white/70 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
        pressed
          ? "bg-white text-black font-semibold"
          : "bg-transparent text-white hover:bg-white/10"
      }`}
    >
      {children}
    </button>
  );
}

function SeasonDetail({ player }: { player: PlayerRecord }) {
  if (!player.seasons.length) {
    return (
      <p className="text-sm text-neutral-600">
        No year-by-year detail yet. Run a full player-records scrape.
      </p>
    );
  }

  return (
    <table className="w-full text-sm text-left">
      <caption className="sr-only">{`${player.name} year-by-year roster and starter points`}</caption>
      <thead>
        <tr className="text-neutral-600 border-b border-neutral-300">
          <th scope="col" className="py-1 pr-3 font-medium">
            Year
          </th>
          <th scope="col" className="py-1 pr-3 font-medium">
            Fantasy team
          </th>
          <th scope="col" className="py-1 pr-3 font-medium">
            NFL
          </th>
          <th scope="col" className="py-1 pr-3 font-medium text-right tabular-nums">
            Starts
          </th>
          <th scope="col" className="py-1 font-medium text-right tabular-nums">
            Avg pts as starter
          </th>
        </tr>
      </thead>
      <tbody>
        {player.seasons.map((season) => {
          const nfl = uniqueTeams(season.nfl);
          return (
            <tr key={`${player.name}-${season.year}`} className="border-b border-neutral-200 last:border-0">
              <td className="py-1.5 pr-3 tabular-nums">{season.year}</td>
              <td className="py-1.5 pr-3">
                {season.fantasy.length
                  ? season.fantasy.map(formatFantasyTeam).join(", ")
                  : "—"}
              </td>
              <td className="py-1.5 pr-3">
                {nfl.length ? (
                  <span className="flex flex-wrap items-center gap-1" title={nfl.join(", ")}>
                    {nfl.map((team, index) => (
                      <TeamLogo
                        key={`${player.name}-${season.year}-${team}-${index}`}
                        src={nflLogoUrl(team)}
                        alt={team}
                        size="sm"
                      />
                    ))}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{season.gs}</td>
              <td className="py-1.5 text-right tabular-nums">
                {season.avgStarterPts == null ? "—" : season.avgStarterPts.toFixed(1)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
