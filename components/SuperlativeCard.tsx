import TeamLogo from "./TeamLogo";
import { logoPublicUrl, nflLogoUrl } from "@/lib/logos";
import {
  isDefenseSubject,
  type AwardDef,
  type SuperlativeDetail,
  type SuperlativeRow,
} from "@/lib/superlatives";

type Portrait = { src: string | null; alt: string; circle: boolean };

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
    }
    return [left, right];
  }
  if (row.subject_type === "week") {
    const winners = detail.winners ?? [];
    if (winners.length > 1) {
      return winners.map((winner) => ({
        src: logoPublicUrl(winner.logo_path),
        alt: winner.owner,
        circle: true,
      }));
    }
    return [
      {
        src: logoPublicUrl(detail.logo_path),
        alt: detail.owners?.[0] || row.subject_name,
        circle: true,
      },
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
  return [{ src: logoPublicUrl(detail.logo_path), alt: row.subject_name, circle: true }];
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

type Props = {
  award: AwardDef;
  places: SuperlativeRow[];
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

function placeLine(awardId: string, place: SuperlativeRow) {
  return (
    <li key={`${awardId}-${place.subject_key}-${place.rank}`}>
      {place.rank}. {place.subject_name}
      <span className="text-white/45"> · {place.display}</span>
    </li>
  );
}

function hasDetail(awardId: string, place: SuperlativeRow) {
  const detail = place.detail;
  if (awardId === "most_fantasy_teams") return (detail.owners?.length ?? 0) > 0;
  if (awardId === "most_auction_dollars") return (detail.seasons?.length ?? 0) > 0;
  if (awardId === "total_earnings") return (detail.lines?.length ?? 0) > 0;
  if (awardId === "nfl_starter_week") return (detail.starters?.length ?? 0) > 0;
  return false;
}

function DetailBody({ awardId, places }: { awardId: string; places: SuperlativeRow[] }) {
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
                    <span className="text-white/45"> · {money(line.amount)}</span>
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

export default function SuperlativeCard({ award, places }: Props) {
  const top = places.slice(0, 10);
  const leader = top[0];
  if (!leader) return null;
  const photos = portrait(leader.detail, leader);
  const showList = top.length > 1;
  const showDetails = top.some((place) => hasDetail(award.id, place));

  return (
    <li className="@container rounded-lg border border-white/20 bg-white/5 px-4 py-4">
      <h2 className="text-lg font-semibold">{award.label}</h2>
      <p className="mt-1 text-sm text-white/55">{award.hint}</p>
      <div className="mt-4 flex flex-col gap-4 @min-[32rem]:flex-row @min-[32rem]:items-start">
        <div className="min-w-0 shrink-0">
          <div className="flex items-end gap-3">
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
          <p className="mt-3 text-xl font-semibold">{leader.subject_name}</p>
          <p className="text-sm text-white/80">{leader.display}</p>
        </div>
        {showList ? (
          <ol className="hidden min-w-0 flex-1 space-y-1 text-sm text-white/70 @min-[32rem]:block">
            {top.map((place) => placeLine(award.id, place))}
          </ol>
        ) : null}
      </div>
      {showList || showDetails ? (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          {showList ? (
            <div className="@min-[32rem]:hidden">
              <Disclosure closed="Top 10" open="Hide top 10">
                <ol className="mt-2 w-full space-y-1 text-sm text-white/70">
                  {top.map((place) => placeLine(award.id, place))}
                </ol>
              </Disclosure>
            </div>
          ) : null}
          {showDetails ? (
            <Disclosure closed="Details" open="Hide details">
              <DetailBody awardId={award.id} places={top} />
            </Disclosure>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
