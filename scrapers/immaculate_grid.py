"""Build the Immaculate Grid answer key and this season's daily puzzles.

Tags come from nflverse weekly stats. Achievements use completed seasons only,
so a published grid does not move during the current year. Team tags include
the season in progress. Existing puzzle days are left alone.

    python scrapers/immaculate_grid.py
    python scrapers/immaculate_grid.py --grids-only
    python scrapers/immaculate_grid.py --self-test
"""

from __future__ import annotations

import argparse
import io
import json
import random
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from league import opening_thursday as _opening_thursday
from nfl_teams import STATS_URL, espn_abbrev
from supabase_client import get_service_client

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / ".cache"
LEAGUE_PATH = ROOT / "data" / "league.json"
FIRST_SEASON = 1999
SKILL = {"QB", "RB", "WR", "TE"}
MIN_ANSWERS = 8
EASTERN = ZoneInfo("America/New_York")

FRANCHISES = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB",
    "TEN", "WSH",
}
EXTRA_TEAMS = {"LVR": "LV"}

RANKINGS = {
    "QB": ((1, "season:qb:1"), (5, "season:qb:top5"), (12, "season:qb:top12")),
    "RB": ((1, "season:rb:1"), (10, "season:rb:top10"), (24, "season:rb:top24")),
    "WR": ((1, "season:wr:1"), (10, "season:wr:top10"), (24, "season:wr:top24")),
    "TE": ((1, "season:te:1"), (5, "season:te:top5"), (12, "season:te:top12")),
}
POINT_TAGS = ((300, "season:ppr300"), (200, "season:ppr200"))
GAME_TAGS = ((50, "game:50"), (40, "game:40"), (30, "game:30"))
CHAINS = (
    tuple(tag for _, tag in RANKINGS["QB"]),
    tuple(tag for _, tag in RANKINGS["RB"]),
    tuple(tag for _, tag in RANKINGS["WR"]),
    tuple(tag for _, tag in RANKINGS["TE"]),
    tuple(tag for _, tag in GAME_TAGS),
    tuple(tag for _, tag in POINT_TAGS),
)
TEAM_TAGS = [f"team:{abbrev}" for abbrev in sorted(FRANCHISES)]
ACHIEVEMENT_TAGS = [tag for chain in CHAINS for tag in chain]

WEEK_COLUMNS = [
    "player_id",
    "player_display_name",
    "player_name",
    "position",
    "season",
    "week",
    "season_type",
    "team",
    "fantasy_points_ppr",
]


def opening_thursday(season: int) -> date:
    return _opening_thursday(season)


def season_end(season: int) -> date:
    return opening_thursday(season) + timedelta(days=122)


def latest_completed(today: date) -> int:
    # Week 18 ends in January, so the season still in progress can be two calendar years back.
    for season in (today.year, today.year - 1, today.year - 2):
        if today > season_end(season):
            return season
    return today.year - 2


def fold_name(name: str) -> str:
    text = name.lower().replace("'", "").replace("’", "").replace(".", "").replace("-", " ")
    return " ".join(text.split())


def franchise(team: str, season: int) -> str | None:
    if not team or team in {"NAN", "NONE", "FA"}:
        return None
    mapped = espn_abbrev(team)
    if not mapped:
        return None
    mapped = EXTRA_TEAMS.get(mapped, mapped)
    if mapped == "HOU" and season < 2002:
        mapped = "TEN"
    if mapped not in FRANCHISES:
        return None
    return mapped


def conflicts(left: str, right: str) -> bool:
    if left == right:
        return True
    return any(left in chain and right in chain for chain in CHAINS)


def grid_ok(rows: list[str], cols: list[str], membership: dict[str, set[str]]) -> bool:
    headers = rows + cols
    if len(headers) != 6 or len(set(headers)) != 6:
        return False
    teams = sum(header.startswith("team:") for header in headers)
    if teams < 2 or 6 - teams < 2:
        return False
    for index, left in enumerate(headers):
        for right in headers[index + 1 :]:
            if conflicts(left, right):
                return False
    for row in rows:
        for col in cols:
            if len(membership.get(row, set()) & membership.get(col, set())) < MIN_ANSWERS:
                return False
    return True


def _sample_achievements(rng: random.Random, pool: list[str], count: int) -> list[str] | None:
    bag = list(pool)
    rng.shuffle(bag)
    picked: list[str] = []
    for tag in bag:
        if any(conflicts(tag, other) for other in picked):
            continue
        picked.append(tag)
        if len(picked) == count:
            return picked
    return None


def choose_grid(day: date, membership: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    """Deterministic for a date and a tag index. Callers must not overwrite a stored day."""
    rng = random.Random(day.toordinal())
    teams = [tag for tag in TEAM_TAGS if len(membership.get(tag, set())) >= MIN_ANSWERS]
    achievements = [tag for tag in ACHIEVEMENT_TAGS if len(membership.get(tag, set())) >= MIN_ANSWERS]
    if len(teams) < 2 or len(achievements) < 2:
        raise SystemExit("Not enough categories to build a grid.")
    for _ in range(8000):
        team_count = rng.choice((2, 2, 2, 3, 3, 4))
        picked_teams = rng.sample(teams, team_count)
        picked_achievements = _sample_achievements(rng, achievements, 6 - team_count)
        if not picked_achievements:
            continue
        headers = picked_teams + picked_achievements
        rng.shuffle(headers)
        rows, cols = headers[:3], headers[3:]
        if grid_ok(rows, cols, membership):
            return rows, cols
    raise SystemExit(f"No valid grid for {day.isoformat()}.")


def download(year: int) -> bytes | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    name = f"stats_player_week_{year}.csv"
    path = CACHE / name
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    req = urllib.request.Request(STATS_URL.format(year=year), headers={"User-Agent": "commissioner-report"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        print(f"  skip {year}: {exc}")
        return None
    path.write_bytes(data)
    return data


def load_weeks(years: list[int]) -> pd.DataFrame:
    frames = []
    for year in years:
        raw = download(year)
        if not raw:
            continue
        header = pd.read_csv(io.BytesIO(raw), nrows=0).columns
        use = [column for column in WEEK_COLUMNS if column in header]
        frame = pd.read_csv(io.BytesIO(raw), usecols=use)
        frames.append(frame)
        print(f"  weekly {year}: {len(frame)} rows")
    if not frames:
        raise SystemExit("No weekly nflverse files downloaded.")
    frame = pd.concat(frames, ignore_index=True)
    frame["player_id"] = frame["player_id"].astype(str).str.strip()
    frame = frame[frame["player_id"].ne("") & frame["player_id"].str.lower().ne("nan")]
    frame["position"] = frame["position"].fillna("").astype(str).str.upper().str.strip()
    frame = frame[frame["position"].isin(SKILL)]
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").fillna(0).astype(int)
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce").fillna(0).astype(int)
    frame["season_type"] = frame.get("season_type", "REG")
    frame["season_type"] = frame["season_type"].fillna("REG").astype(str).str.upper().str.strip()
    frame = frame[frame["season_type"].isin(["REG", "POST"])]
    frame["points"] = pd.to_numeric(frame["fantasy_points_ppr"], errors="coerce").fillna(0.0)
    raw_team = frame["team"].map(lambda value: "" if pd.isna(value) else str(value).strip().upper())
    mapped = [
        franchise(team, int(season))
        for team, season in zip(raw_team.tolist(), frame["season"].tolist())
    ]
    unknown = raw_team[(raw_team.ne("")) & pd.Series(mapped, index=frame.index).isna()]
    if not unknown.empty:
        print("  unmapped teams:", ", ".join(f"{team} ({count})" for team, count in unknown.value_counts().head(8).items()))
    frame = frame.assign(franchise=mapped)
    frame = frame[frame["franchise"].notna()]
    return frame


def _clean_name(display: object, short: object) -> str:
    for value in (display, short):
        if isinstance(value, str) and value.strip() and value.strip().lower() != "nan":
            return " ".join(value.split())
    return ""


def build_index(frame: pd.DataFrame, completed_through: int) -> tuple[list[dict], list[dict], dict[str, set[str]]]:
    named = frame.sort_values(["season", "week"]).groupby("player_id", as_index=False).tail(1)
    names = {
        str(row.player_id): _clean_name(
            getattr(row, "player_display_name", ""),
            getattr(row, "player_name", ""),
        )
        for row in named.itertuples(index=False)
    }
    spans = frame.groupby("player_id")["season"].agg(["min", "max"])
    pos_counts = frame.groupby(["player_id", "position"]).size().reset_index(name="n")
    pos_counts = pos_counts.sort_values(["player_id", "n"], ascending=[True, False]).drop_duplicates("player_id")
    positions = dict(zip(pos_counts["player_id"].astype(str), pos_counts["position"]))

    regular = frame[(frame["season_type"] == "REG") & (frame["season"] <= completed_through)].copy()
    fame = regular.groupby("player_id")["points"].sum()
    tags: set[tuple[str, str]] = set()
    for player_id, team in frame[["player_id", "franchise"]].drop_duplicates().itertuples(index=False):
        tags.add((str(player_id), f"team:{team}"))

    if not regular.empty:
        totals = regular.groupby(["player_id", "season"], as_index=False)["points"].sum()
        primary_counts = regular.groupby(["player_id", "season", "position"]).size().reset_index(name="n")
        primary_counts = primary_counts.sort_values(
            ["player_id", "season", "n"],
            ascending=[True, True, False],
        ).drop_duplicates(["player_id", "season"])
        totals = totals.merge(
            primary_counts[["player_id", "season", "position"]],
            on=["player_id", "season"],
            how="left",
        )
        totals["rank"] = totals.groupby(["season", "position"])["points"].rank(method="min", ascending=False)
        for row in totals.itertuples(index=False):
            player_id = str(row.player_id)
            for cutoff, tag in RANKINGS.get(row.position, ()):
                if row.rank <= cutoff:
                    tags.add((player_id, tag))
            for cutoff, tag in POINT_TAGS:
                if row.points >= cutoff:
                    tags.add((player_id, tag))
        peaks = regular.groupby("player_id")["points"].max()
        for player_id, peak in peaks.items():
            for cutoff, tag in GAME_TAGS:
                if float(peak) >= cutoff:
                    tags.add((str(player_id), tag))

    players = []
    kept_ids = set()
    for player_id, name in names.items():
        if not name or player_id not in positions:
            continue
        span = spans.loc[player_id] if player_id in spans.index else None
        if span is None:
            continue
        kept_ids.add(player_id)
        career = float(fame.get(player_id, 0.0)) if hasattr(fame, "get") else 0.0
        players.append(
            {
                "id": player_id,
                "name": name,
                "pos": positions[player_id],
                "year_min": int(span["min"]),
                "year_max": int(span["max"]),
                "fame": round(career, 2),
                "search_name": fold_name(name),
            }
        )
    tags = {pair for pair in tags if pair[0] in kept_ids}
    tag_rows = [{"player_id": player_id, "tag": tag} for player_id, tag in sorted(tags)]
    membership: dict[str, set[str]] = defaultdict(set)
    for player_id, tag in tags:
        membership[tag].add(player_id)
    return players, tag_rows, membership


def sanity_check(players: list[dict], tags: set[tuple[str, str]]) -> None:
    by_fold = defaultdict(list)
    for player in players:
        by_fold[fold_name(player["name"])].append(player)
    mahomes = sorted(by_fold.get("patrick mahomes", []), key=lambda player: player["fame"], reverse=True)
    if not mahomes:
        raise SystemExit("Patrick Mahomes is missing from the answer key.")
    his = {tag for player_id, tag in tags if player_id == mahomes[0]["id"]}
    for required in ("team:KC", "season:qb:1", "game:40"):
        if required not in his:
            raise SystemExit(f"Patrick Mahomes is missing {required}.")
    brady = by_fold.get("tom brady", [])
    if not brady:
        raise SystemExit("Tom Brady is missing from the answer key.")
    brady_tags = {tag for player_id, tag in tags if player_id == brady[0]["id"]}
    for required in ("team:NE", "team:TB"):
        if required not in brady_tags:
            raise SystemExit(f"Tom Brady is missing {required}.")
    # A tag means the player did it at least once, so repeat winners count once.
    qb1 = sum(1 for _, tag in tags if tag == "season:qb:1")
    if qb1 < 10:
        raise SystemExit(f"Only {qb1} players were tagged as a QB1.")


def load_league() -> dict:
    return json.loads(LEAGUE_PATH.read_text())


def today_et() -> date:
    return datetime.now(EASTERN).date()


def load_through_year(today: date, league: dict) -> int:
    start = date.fromisoformat(league["grid"]["start"])
    current = int(league["current_season"])
    opener = opening_thursday(today.year)
    started = today.year if today >= opener else today.year - 1
    return max(current, start.year, started)


def days_due(start: date, end: date, today: date) -> list[date]:
    last = min(end, today)
    if last < start:
        return []
    days = []
    day = start
    while day <= last:
        days.append(day)
        day += timedelta(days=1)
    return days


def puzzles_for(league: dict, today: date, membership: dict[str, set[str]]) -> list[dict]:
    start = date.fromisoformat(league["grid"]["start"])
    end = date.fromisoformat(league["grid"]["end"])
    season = start.year
    rows = []
    for day in days_due(start, end, today):
        grid_rows, grid_cols = choose_grid(day, membership)
        rows.append(
            {
                "played_on": day.isoformat(),
                "rows": grid_rows,
                "cols": grid_cols,
                "season": season,
            }
        )
    return rows


def _batches(rows: list[dict], size: int):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def tag_count(client) -> int:
    result = client.table("grid_tags").select("player_id", count="exact", head=True).execute()
    return int(result.count or 0)


def clear_tags(client) -> None:
    for _ in range(200):
        count = tag_count(client)
        if count == 0:
            return
        client.table("grid_tags").delete().neq("player_id", "").execute()
        after = tag_count(client)
        print(f"  tags {count} -> {after}")
        if after >= count:
            raise SystemExit("Could not clear grid_tags. Apply the Immaculate Grid migration with the service role.")
    raise SystemExit("grid_tags did not clear.")


def store_index(client, players: list[dict], tag_rows: list[dict]) -> None:
    print(f"  upserting {len(players)} players")
    for batch in _batches(players, 200):
        client.table("grid_players").upsert(batch, on_conflict="id").execute()
    print("  replacing tags")
    clear_tags(client)
    for batch in _batches(tag_rows, 500):
        client.table("grid_tags").upsert(batch, on_conflict="player_id,tag").execute()
    print(f"  stored {len(tag_rows)} tags")


def store_puzzles(client, puzzles: list[dict]) -> None:
    if not puzzles:
        print("  no grids due")
        return
    for batch in _batches(puzzles, 100):
        client.table("grids").upsert(batch, on_conflict="played_on", ignore_duplicates=True).execute()
    print(f"  ensured {len(puzzles)} grids through today")


def load_membership(client) -> dict[str, set[str]]:
    membership: dict[str, set[str]] = defaultdict(set)
    page = 1000
    offset = 0
    while True:
        result = (
            client.table("grid_tags")
            .select("player_id, tag")
            .order("player_id")
            .order("tag")
            .range(offset, offset + page - 1)
            .execute()
        )
        rows = result.data or []
        for row in rows:
            membership[str(row["tag"])].add(str(row["player_id"]))
        if len(rows) < page:
            break
        offset += page
    if not membership:
        raise SystemExit("grid_tags is empty. Run python scrapers/immaculate_grid.py once to build the answer key.")
    return membership


def refresh_tags(client, today: date, league: dict) -> dict[str, set[str]]:
    through = load_through_year(today, league)
    print(f"Loading nflverse weeks {FIRST_SEASON}–{through}")
    frame = load_weeks(list(range(FIRST_SEASON, through + 1)))
    completed = latest_completed(today)
    print(f"Tagging achievements through {completed}")
    players, tag_rows, membership = build_index(frame, completed)
    tag_pairs = {(row["player_id"], row["tag"]) for row in tag_rows}
    sanity_check(players, tag_pairs)
    for tag in ("team:KC", "season:rb:top10", "game:40", "game:50", "season:ppr300"):
        print(f"  {tag}: {len(membership.get(tag, set()))}")
    store_index(client, players, tag_rows)
    return membership


def self_test() -> None:
    assert opening_thursday(2024) == date(2024, 9, 5)
    assert opening_thursday(2025) == date(2025, 9, 4)
    assert opening_thursday(2026) == date(2026, 9, 10)
    assert season_end(2026) == date(2027, 1, 10)
    assert latest_completed(date(2026, 10, 29)) == 2025
    assert latest_completed(date(2027, 1, 10)) == 2025
    assert latest_completed(date(2027, 1, 11)) == 2026
    league = load_league()
    assert league["grid"]["start"] == opening_thursday(2026).isoformat()
    assert league["grid"]["end"] == season_end(2026).isoformat()
    assert fold_name("A.J. Brown") == "aj brown"
    assert fold_name("Ja'Marr Chase") == "jamarr chase"
    assert fold_name("Jaxon Smith-Njigba") == "jaxon smith njigba"
    assert franchise("OAK", 2000) == "LV"
    assert franchise("SD", 2010) == "LAC"
    assert franchise("STL", 2010) == "LAR"
    assert franchise("LA", 2018) == "LAR"
    assert franchise("HOU", 1999) == "TEN"
    assert franchise("HOU", 2024) == "HOU"
    assert franchise("WAS", 2024) == "WSH"

    ranked = pd.DataFrame(
        {
            "player_id": ["a", "b", "c", "d"],
            "season": [1999, 1999, 1999, 1999],
            "position": ["RB", "RB", "RB", "RB"],
            "points": [10.0, 10.0, 8.0, 1.0],
        }
    )
    ranked["rank"] = ranked.groupby(["season", "position"])["points"].rank(method="min", ascending=False)
    assert set(ranked.loc[ranked["rank"] <= 1, "player_id"]) == {"a", "b"}
    assert set(ranked.loc[ranked["rank"] <= 2, "player_id"]) == {"a", "b"}

    shared = {f"p{i}" for i in range(30)}
    membership = {tag: set(shared) for tag in TEAM_TAGS + ACHIEVEMENT_TAGS}
    first = choose_grid(date(2026, 10, 29), membership)
    assert first == choose_grid(date(2026, 10, 29), membership)
    assert grid_ok(first[0], first[1], membership)
    assert choose_grid(date(2026, 9, 10), membership) != first
    membership["team:BAL"] = {f"b{i}" for i in range(20)}
    membership["season:rb:top10"] = {f"r{i}" for i in range(20)}
    rows, cols = choose_grid(date(2026, 10, 29), membership)
    pairs = {(row, col) for row in rows for col in cols}
    assert ("team:BAL", "season:rb:top10") not in pairs
    assert ("season:rb:top10", "team:BAL") not in pairs
    assert grid_ok(rows, cols, membership)
    print("immaculate grid ok")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grids-only", action="store_true", help="Insert missing daily grids from tags already stored.")
    parser.add_argument("--tags-only", action="store_true", help="Rebuild players and tags without writing grids.")
    parser.add_argument("--self-test", action="store_true", help="Run calendar, ranking, and generator checks.")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.grids_only and args.tags_only:
        raise SystemExit("Pick one of --grids-only or --tags-only.")

    league = load_league()
    today = today_et()
    client = get_service_client()
    if args.grids_only:
        membership = load_membership(client)
    else:
        membership = refresh_tags(client, today, league)
    if not args.tags_only:
        store_puzzles(client, puzzles_for(league, today, membership))


if __name__ == "__main__":
    main()
