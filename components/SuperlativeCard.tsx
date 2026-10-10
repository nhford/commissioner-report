"use client";

import { useState } from "react";
import TeamLogo from "./TeamLogo";
import { dollarText, earningsBoard } from "@/lib/inflation";
import { logoPublicUrl, nflLogoUrl } from "@/lib/logos";
import {
  TILE_FILTERS,
  changedAt,
  isDefenseSubject,
  rateChange,
  tileApplies,
  tileChecked,
  tileEmptiesLocally,
  type AwardDef,
  type DepartedPlace,
  type SuperlativeDetail,
  type SuperlativeFilters,
  type SuperlativeRow,
} from "@/lib/superlatives";

type Portrait = { src: string | null; alt: string; circle: boolean };

const JACK_PORTRAIT = "/images/owners/jack.png";

function withOwnerPhoto(portrait: Portrait): Portrait {
  if (portrait.alt !== "Jack") return portrait;
  return { ...portrait, src: JACK_PORTRAIT, circle: true };
}

function isDefense(
  name: string | null | undefined,
  pos: string | null | undefined,
) {
  return pos === "D/ST" || pos === "DST" || Boolean(name && /\bD\/ST\b/.test(name));
}

function personSrc(
  name: string | null | undefined,
  pos: string | null | undefined,
  nflTeam: string | null | undefined,
  photo: string | null | undefined,
  logo: string | null | undefined,
): Portrait {
  const defense = isDefense(name, pos);
  if (defense && nflTeam) {
    return { src: nflLogoUrl(nflTeam), alt: name || "D/ST", circle: true };
  }
  if (photo) return { src: logoPublicUrl(photo), alt: name || "Player", circle: false };
  return { src: logoPublicUrl(logo), alt: name || "Player", circle: false };
}

function portrait(detail: SuperlativeDetail, row: SuperlativeRow): Portrait[] {
  if (row.subject_type === "duo") {
    const players = detail.player_id != null;
    const left = personSrc(
      detail.player_name,
      detail.pos,
      detail.nfl_team,
      detail.photo_path,
      detail.logo_path,
    );
    const right = personSrc(
      detail.partner_name,
      detail.partner_pos,
      detail.partner_nfl_team,
      detail.partner_photo_path,
      detail.partner_logo_path,
    );
    if (!players) {
      left.circle = true;
      right.circle = true;
      left.alt = detail.player_name || row.subject_name;
      right.alt = detail.partner_name || "Partner";
      return [withOwnerPhoto(left), withOwnerPhoto(right)];
    }
    return [left, right];
  }
  if (row.subject_type === "week") {
    const winners = detail.winners ?? [];
    if (winners.length > 1) {
      return winners.map((winner) =>
        withOwnerPhoto({
          src: logoPublicUrl(winner.logo_path),
          alt: winner.owner,
          circle: true,
        }),
      );
    }
    return [
      withOwnerPhoto({
        src: logoPublicUrl(detail.logo_path),
        alt: detail.owners?.[0] || row.subject_name,
        circle: true,
      }),
    ];
  }
  if (row.subject_type === "nfl" && detail.nfl_team) {
    return [{ src: nflLogoUrl(detail.nfl_team), alt: detail.nfl_team, circle: true }];
  }
  if (isDefenseSubject(row.subject_name, detail) && detail.nfl_team) {
    return [{ src: nflLogoUrl(detail.nfl_team), alt: row.subject_name, circle: true }];
  }
  if (detail.photo_path) {
    return [{ src: logoPublicUrl(detail.photo_path), alt: row.subject_name, circle: false }];
  }
  const logo = {
    src: logoPublicUrl(detail.logo_path),
    alt: row.subject_name,
    circle: true,
  };
  return [row.subject_type === "player" ? logo : withOwnerPhoto(logo)];
}

function starterLabel(starter: NonNullable<SuperlativeDetail["starters"]>[number]) {
  const points =
    starter.points == null
      ? null
      : String(starter.points).replace(/\.0$/, "");
  return [starter.pos, starter.owner, points].filter(Boolean).join(" · ");
}

function money(amount: number) {
  return Number.isInteger(amount) ? `$${amount}` : `$${amount.toFixed(2)}`;
}

function pointsLabel(amount: number) {
  const text = Number.isInteger(amount)
    ? String(amount)
    : amount.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  return `${text} pts`;
}

type Props = {
  award: AwardDef;
  places: SuperlativeRow[];
  hideDefense: boolean;
  asOfSeason: number;
  asOfWeek: number;
  leaving?: DepartedPlace[];
  filters?: SuperlativeFilters;
};

function Disclosure({
  closed,
  open,
  children,
}: {
  closed: string;
  open: string;
  children: React.ReactNode;
}) {
  return (
    <details className="group w-fit open:w-full">
      <summary className="min-h-9 w-fit cursor-pointer list-none text-sm text-white/80 underline decoration-white/30 underline-offset-2 [&::-webkit-details-marker]:hidden">
        <span className="group-open:hidden">{closed}</span>
        <span className="hidden group-open:inline">{open}</span>
      </summary>
      {children}
    </details>
  );
}

function duoName(name: string) {
  const split = name.split(" & ");
  if (split.length < 2) return name;
  return (
    <>
      {split[0]} &<br />
      {split.slice(1).join(" & ")}
    </>
  );
}

function Delta({ text }: { text: string | null }) {
  if (!text) return null;
  return <span className="font-normal text-white/70"> ({text})</span>;
}

function placeLine(
  awardId: string,
  rank: number,
  name: string,
  display: string,
  fresh: boolean,
  leaving: boolean,
  delta: string | null,
) {
  const marked = fresh || leaving;
  return (
    <li
      key={`${awardId}-${leaving ? "left" : "here"}-${name}-${rank}`}
      className={
        leaving
          ? "font-bold text-white line-through"
          : fresh
            ? "font-bold text-white"
            : undefined
      }
    >
      {rank}. {name}
      <span className={marked ? "text-white" : "text-white/45"}> · {display}</span>
      {fresh ? <Delta text={delta} /> : null}
    </li>
  );
}

function listedLines(
  awardId: string,
  places: SuperlativeRow[],
  leaving: DepartedPlace[],
  fresh: (place: SuperlativeRow) => boolean,
  hideDefense: boolean,
) {
  const rows: {
    rank: number;
    name: string;
    display: string;
    fresh: boolean;
    leaving: boolean;
    delta: string | null;
  }[] = [
    ...places.map((place) => ({
      rank: place.rank,
      name: place.subject_name,
      display: place.display,
      fresh: fresh(place),
      leaving: false,
      delta: rateChange(place, hideDefense),
    })),
    ...leaving.map((place) => ({
      rank: place.rank,
      name: place.subject_name,
      display: place.display,
      fresh: true,
      leaving: true,
      delta: null,
    })),
  ];
  rows.sort((left, right) => left.rank - right.rank || Number(right.leaving) - Number(left.leaving));
  return rows.map((row) =>
    placeLine(awardId, row.rank, row.name, row.display, row.fresh, row.leaving, row.delta),
  );
}

function hasDetail(awardId: string, place: SuperlativeRow) {
  const detail = place.detail;
  if (awardId === "most_fantasy_teams") {
    return (detail.owners?.length ?? 0) > 0 || (detail.seasons?.length ?? 0) > 0;
  }
  if (awardId === "least_fantasy_teams") return (detail.seasons?.length ?? 0) > 1;
  if (awardId === "most_auction_dollars") return (detail.seasons?.length ?? 0) > 0;
  if (awardId === "total_earnings") return (detail.lines?.length ?? 0) > 0;
  if (awardId === "nfl_starter_week") return (detail.starters?.length ?? 0) > 0;
  if (awardId === "projection_over_streak" || awardId === "projection_under_streak") {
    return (detail.weeks?.length ?? 0) > 0;
  }
  return false;
}

function DetailBody({
  awardId,
  places,
  wholeDollars,
}: {
  awardId: string;
  places: SuperlativeRow[];
  wholeDollars?: boolean;
}) {
  const detailed = places.filter((place) => hasDetail(awardId, place));
  return (
    <div className="mt-2 w-full space-y-3 text-sm text-white/75">
      {detailed.map((place) => {
        const detail = place.detail;
        return (
          <div key={`${awardId}-detail-${place.rank}`}>
            {detailed.length > 1 ? (
              <p className="font-medium text-white">
                {place.rank}. {place.subject_name}
              </p>
            ) : null}
            {awardId === "most_fantasy_teams" && detail.owners?.length ? (
              <ul className="mt-1 space-y-0.5">
                {detail.owners.map((owner) => (
                  <li key={`${place.rank}-${owner}`}>{owner}</li>
                ))}
              </ul>
            ) : null}
            {awardId === "most_fantasy_teams" && detail.seasons?.some((season) => season.games != null) ? (
              <ul className="mt-1 space-y-0.5">
                {detail.seasons.map((season) => (
                  <li key={`${place.rank}-${season.season}`}>
                    {season.season}
                    <span className="text-white/45">
                      {" "}
                      · {season.games} {season.games === 1 ? "game" : "games"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
            {awardId === "least_fantasy_teams" && detail.seasons?.length ? (
              <ul className="mt-1 space-y-0.5">
                {detail.seasons.map((season) => (
                  <li key={`${place.rank}-${season.season}`}>
                    {season.season}
                    <span className="text-white/45"> · {pointsLabel(season.amount)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {awardId === "most_auction_dollars" && detail.seasons?.length ? (
              <ul className="mt-1 space-y-0.5">
                {detail.seasons.map((season) => (
                  <li key={`${place.rank}-${season.season}`}>
                    {season.season}
                    <span className="text-white/45"> · {money(season.amount)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {awardId === "total_earnings" && detail.lines?.length ? (
              <ul className="mt-1 space-y-0.5">
                {detail.lines.map((line) => (
                  <li key={`${place.rank}-${line.label}`}>
                    {line.label}
                    <span className="text-white/45">
                      {" "}
                      · {wholeDollars ? dollarText(line.amount) : money(line.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
            {(awardId === "projection_over_streak" || awardId === "projection_under_streak") &&
            detail.weeks?.length ? (
              <ul className="mt-1 space-y-0.5">
                {detail.weeks.map((week) => (
                  <li key={`${place.rank}-${week.season}-${week.week}`}>
                    {week.season} Wk {week.week}
                    <span className="text-white/45">
                      {week.bye
                        ? " · BYE"
                        : ` · ${pointsLabel(week.points ?? 0)} vs ${pointsLabel(week.projected ?? 0)}`}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
            {awardId === "nfl_starter_week" && detail.starters?.length ? (
              <ul className="mt-1 space-y-0.5">
                {detail.starters.map((starter) => (
                  <li key={`${place.rank}-${starter.name}-${starter.owner}`}>
                    {starter.name}
                    {starterLabel(starter) ? (
                      <span className="text-white/45"> · {starterLabel(starter)}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function Check({
  checked,
  label,
  title,
  onClick,
}: {
  checked: boolean;
  label: string;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      title={title}
      onClick={onClick}
      className="flex min-h-9 shrink-0 items-center gap-2 whitespace-nowrap text-sm text-white"
    >
      <span
        aria-hidden
        className={`grid h-4 w-4 place-items-center rounded border text-[10px] leading-none ${
          checked ? "border-white bg-white font-bold text-black" : "border-white/70 bg-transparent"
        }`}
      >
        {checked ? "✓" : ""}
      </span>
      {label}
    </button>
  );
}

function localTileId(awardId: string, param: string) {
  return `hide-${awardId}-${param}`;
}

function localTileCss(id: string) {
  return `#${id}:checked ~ .tile-tools label[for="${id}"] > span{border-color:#fff;background:#fff;color:#000}#${id}:checked ~ .tile-tools label[for="${id}"] > span::before{content:"✓"}#${id}:checked ~ .owner-board{display:none}`;
}

function TileCheck({
  filters,
  name,
  label,
  checked,
  title,
}: {
  filters: SuperlativeFilters;
  name: string;
  label: string;
  checked: boolean;
  title: string;
}) {
  return (
    <form action="/superlatives" method="get" className="w-fit">
      <input type="hidden" name="from" value={filters.fromYear} />
      <input type="hidden" name="to" value={filters.toYear} />
      {filters.owner ? <input type="hidden" name="owner" value={filters.owner} /> : null}
      <input type="hidden" name="players" value={filters.players ? "1" : "0"} />
      <input type="hidden" name="teams" value={filters.teams ? "1" : "0"} />
      <input type="hidden" name="dst" value={filters.hideDefense ? "1" : "0"} />
      <input type="hidden" name="latest" value={filters.sortLatest ? "1" : "0"} />
      {TILE_FILTERS.filter((filter) => filter.param !== name).map((filter) => (
        <input
          key={filter.param}
          type="hidden"
          name={filter.param}
          value={filters.tiles[filter.param] ? "1" : "0"}
        />
      ))}
      <button
        type="submit"
        name={name}
        value={checked ? "0" : "1"}
        aria-pressed={checked}
        title={title}
        className="flex min-h-9 shrink-0 items-center gap-2 whitespace-nowrap text-sm text-white"
      >
        <span
          aria-hidden
          className={`grid h-4 w-4 place-items-center rounded border text-[10px] leading-none ${
            checked ? "border-white bg-white font-bold text-black" : "border-white/70 bg-transparent"
          }`}
        >
          {checked ? "✓" : ""}
        </span>
        {label}
      </button>
    </form>
  );
}

export default function SuperlativeCard({
  award,
  places,
  hideDefense,
  asOfSeason,
  asOfWeek,
  leaving = [],
  filters,
}: Props) {
  const [adjustEarnings, setAdjustEarnings] = useState(false);
  const earningsAdjusted = award.id === "total_earnings" && adjustEarnings;
  const keshavFilter = TILE_FILTERS.find(
    (filter) => filter.param === "keshav" && filter.awardId === award.id,
  );
  const keshavOn = Boolean(
    filters &&
      keshavFilter &&
      tileChecked(filters, "keshav") &&
      tileApplies(keshavFilter, filters.owner) &&
      !tileEmptiesLocally(keshavFilter, filters.owner),
  );
  const top =
    award.id === "total_earnings"
      ? earningsBoard(places, adjustEarnings, keshavOn)
      : places.slice(0, 10);
  const tileFilters = filters
    ? TILE_FILTERS.filter(
        (filter) => filter.awardId === award.id && tileApplies(filter, filters.owner),
      )
    : [];
  const localFilters = filters
    ? tileFilters.filter((filter) => tileEmptiesLocally(filter, filters.owner))
    : [];
  const remoteFilters = tileFilters.filter(
    (filter) => !filters || !tileEmptiesLocally(filter, filters.owner),
  );
  const leader = top[0];
  if (!leader) return null;
  const photos = portrait(leader.detail, leader);
  const showList = top.length > 1;
  const showDetails = top.some((place) => hasDetail(award.id, place));
  const fresh = (place: SuperlativeRow) => {
    const [season, week] = changedAt(place, hideDefense);
    return season === asOfSeason && week === asOfWeek && asOfWeek > 0;
  };
  const leaderFresh = fresh(leader);

  return (
    <li className="@container rounded-lg border border-white/20 bg-white/5 px-4 py-4">
      <h2 className="text-lg font-semibold">{award.label}</h2>
      <p className="mt-1 text-sm text-white/55">
        {filters?.owner && award.ownerHint ? award.ownerHint : award.hint}
      </p>
      {filters
        ? localFilters.map((filter) => (
            <input
              key={filter.param}
              id={localTileId(award.id, filter.param)}
              type="checkbox"
              className="sr-only"
              defaultChecked={tileChecked(filters, filter.param)}
            />
          ))
        : null}
      {award.id === "total_earnings" || tileFilters.length ? (
        <div className="tile-tools mt-2 flex flex-row flex-nowrap items-center gap-x-4">
          {award.id === "total_earnings" ? (
            <Check
              checked={adjustEarnings}
              label="Inflation adjusted"
              title="Restates each payout in August 2026 dollars using CPI-U for the month of that week"
              onClick={() => setAdjustEarnings((checked) => !checked)}
            />
          ) : null}
          {localFilters.map((filter) => (
            <label
              key={filter.param}
              htmlFor={localTileId(award.id, filter.param)}
              title={filter.localTitle ?? filter.title}
              className="flex min-h-9 w-fit cursor-pointer items-center gap-2 text-sm text-white"
            >
              <span
                aria-hidden
                className="grid h-4 w-4 place-items-center rounded border border-white/70 text-[10px] leading-none font-bold"
              />
              {filter.label}
            </label>
          ))}
          {filters
            ? remoteFilters.map((filter) => (
                <TileCheck
                  key={filter.param}
                  filters={filters}
                  name={filter.param}
                  label={filter.label}
                  checked={tileChecked(filters, filter.param)}
                  title={filter.title}
                />
              ))
            : null}
        </div>
      ) : null}
      {localFilters.length ? (
        <style>
          {localFilters
            .map((filter) => localTileCss(localTileId(award.id, filter.param)))
            .join("")}
        </style>
      ) : null}
      <div className={localFilters.length ? "owner-board" : undefined}>
      <div className="mt-4 flex items-start gap-2 @min-[32rem]:gap-4">
        <div className="w-[38%] max-w-24 shrink-0 @min-[32rem]:w-auto @min-[32rem]:max-w-none">
          <div className="flex items-end gap-1 @min-[32rem]:gap-3">
            {photos.map((photo, index) => (
              <TeamLogo
                key={`${award.id}-${index}`}
                src={photo.src}
                alt={photo.alt}
                size="lg"
                circle={photo.circle}
              />
            ))}
          </div>
          <p className={`mt-1.5 text-sm leading-tight @min-[32rem]:mt-3 @min-[32rem]:text-xl ${leaderFresh ? "font-bold" : "font-semibold"}`}>
            {award.id === "player_duo_starts"
              ? duoName(leader.subject_name)
              : leader.subject_name}
          </p>
          <p className={`text-xs leading-tight @min-[32rem]:text-sm ${leaderFresh ? "font-bold text-white" : "text-white/80"}`}>
            {leader.display}
            {leaderFresh ? <Delta text={rateChange(leader, hideDefense)} /> : null}
          </p>
        </div>
        {showList || leaving.length ? (
          <ol className="min-w-0 flex-1 space-y-0.5 text-[11px] leading-tight text-white/70 @min-[32rem]:space-y-1 @min-[32rem]:text-sm @min-[32rem]:leading-normal">
            {listedLines(award.id, top, leaving, fresh, hideDefense)}
          </ol>
        ) : null}
      </div>
      {showDetails ? (
        <div className="mt-3">
          <Disclosure closed="Details" open="Hide details">
            <DetailBody awardId={award.id} places={top} wholeDollars={earningsAdjusted} />
          </Disclosure>
        </div>
      ) : null}
      </div>
    </li>
  );
}
