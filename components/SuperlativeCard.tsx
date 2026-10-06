"use client";

import { useState } from "react";
import TeamLogo from "./TeamLogo";
import { logoPublicUrl, nflLogoUrl } from "@/lib/logos";
import {
  isDefenseSubject,
  type AwardDef,
  type SuperlativeDetail,
  type SuperlativeRow,
} from "@/lib/superlatives";

function personSrc(
  name: string | null | undefined,
  pos: string | null | undefined,
  nflTeam: string | null | undefined,
  photo: string | null | undefined,
  logo: string | null | undefined,
) {
  const defense =
    pos === "D/ST" || pos === "DST" || Boolean(name && /\bD\/ST\b/.test(name));
  if (defense && nflTeam) return nflLogoUrl(nflTeam);
  if (photo) return logoPublicUrl(photo);
  return logoPublicUrl(logo);
}

function portrait(detail: SuperlativeDetail, row: SuperlativeRow) {
  if (row.subject_type === "duo") {
    return [
      {
        src: personSrc(
          detail.player_name,
          detail.pos,
          detail.nfl_team,
          detail.photo_path,
          detail.logo_path,
        ),
        alt: detail.player_name || row.subject_name,
      },
      {
        src: personSrc(
          detail.partner_name,
          detail.partner_pos,
          detail.partner_nfl_team,
          detail.partner_photo_path,
          detail.partner_logo_path,
        ),
        alt: detail.partner_name || "Partner",
      },
    ];
  }
  if (row.subject_type === "week") {
    const winners = detail.winners ?? [];
    if (winners.length > 1) {
      return winners.map((winner) => ({
        src: logoPublicUrl(winner.logo_path),
        alt: winner.owner,
      }));
    }
    return [
      {
        src: logoPublicUrl(detail.logo_path),
        alt: detail.owners?.[0] || row.subject_name,
      },
    ];
  }
  if (row.subject_type === "nfl" && detail.nfl_team) {
    return [{ src: nflLogoUrl(detail.nfl_team), alt: detail.nfl_team }];
  }
  if (isDefenseSubject(row.subject_name, detail) && detail.nfl_team) {
    return [{ src: nflLogoUrl(detail.nfl_team), alt: row.subject_name }];
  }
  if (detail.photo_path) {
    return [{ src: logoPublicUrl(detail.photo_path), alt: row.subject_name }];
  }
  return [{ src: logoPublicUrl(detail.logo_path), alt: row.subject_name }];
}

function starterLabel(starter: NonNullable<SuperlativeDetail["starters"]>[number]) {
  const points =
    starter.points == null
      ? null
      : String(starter.points).replace(/\.0$/, "");
  return [starter.pos, starter.owner, points].filter(Boolean).join(" · ");
}

type Props = {
  award: AwardDef;
  places: SuperlativeRow[];
};

export default function SuperlativeCard({ award, places }: Props) {
  const [showTop, setShowTop] = useState(false);
  const [showDetail, setShowDetail] = useState(false);
  const shown = places.slice(0, showTop ? 10 : 3);
  const leader = shown[0];
  if (!leader) return null;
  const photos = portrait(leader.detail, leader);
  const starterPlaces =
    award.id === "nfl_starter_week"
      ? shown.filter((place) => (place.detail.starters ?? []).length > 0)
      : [];

  return (
    <li className="rounded-lg border border-white/20 bg-white/5 px-4 py-4">
      <h2 className="text-lg font-semibold">{award.label}</h2>
      <p className="mt-1 text-sm text-white/55">{award.hint}</p>
      <div className="mt-4 flex items-end gap-3">
        {photos.map((photo, index) => (
          <TeamLogo
            key={`${award.id}-${index}`}
            src={photo.src}
            alt={photo.alt}
            size="lg"
          />
        ))}
      </div>
      <p className="mt-3 text-xl font-semibold">{leader.subject_name}</p>
      <p className="text-sm text-white/80">{leader.display}</p>
      {shown.length > 1 ? (
        <ol className="mt-3 space-y-1 text-sm text-white/70">
          {shown.slice(1).map((place) => (
            <li key={`${award.id}-${place.subject_key}-${place.rank}`}>
              {place.rank}. {place.subject_name}
              <span className="text-white/45"> · {place.display}</span>
            </li>
          ))}
        </ol>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {places.length > 3 ? (
          <button
            type="button"
            onClick={() => setShowTop((open) => !open)}
            aria-expanded={showTop}
            className="min-h-9 text-sm text-white/80 underline decoration-white/30 underline-offset-2"
          >
            {showTop ? "Show podium" : "Top 10"}
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => setShowDetail((open) => !open)}
          aria-expanded={showDetail}
          className="min-h-9 text-sm text-white/80 underline decoration-white/30 underline-offset-2"
        >
          {showDetail ? "Hide details" : "Details"}
        </button>
      </div>
      {showDetail ? (
        starterPlaces.length > 0 ? (
          <div className="mt-2 space-y-3 text-sm text-white/75">
            {starterPlaces.map((place) => (
              <div key={`${award.id}-starters-${place.rank}`}>
                <p className="font-medium text-white">
                  {place.rank}. {place.subject_name}
                  <span className="font-normal text-white/50"> · {place.display}</span>
                </p>
                <ul className="mt-1 space-y-0.5">
                  {(place.detail.starters ?? []).map((starter) => (
                    <li key={`${place.rank}-${starter.name}-${starter.owner}`}>
                      {starter.name}
                      {starterLabel(starter) ? (
                        <span className="text-white/45"> · {starterLabel(starter)}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-white/55">More detail is coming.</p>
        )
      ) : null}
    </li>
  );
}
