"""The NFL team a player was on in a given week.

ESPN's proTeam on a historical box score is often the club he joined later.
Weekly rosters and weekly stats from nflverse record the team for that week.
"""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / ".cache"

ROSTER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "weekly_rosters/roster_weekly_{year}.csv"
)
STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{year}.csv"
)

# nflverse abbreviations that ESPN fantasy does not use.
NFLVERSE_TO_ESPN = {
    "LA": "LAR",
    "WAS": "WSH",
    "JAC": "JAX",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}

def espn_abbrev(team: str | None) -> str | None:
    if team is None:
        return None
    text = str(team).strip().upper()
    if text in {"", "NONE", "NAN"}:
        return None
    return NFLVERSE_TO_ESPN.get(text, text)


def _espn_id(value) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _week(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def is_defense(pos: str | None, name: str | None = None) -> bool:
    if pos in {"D/ST", "DST"}:
        return True
    return bool(name and "D/ST" in name)


class WeekTeams:
    """Team by ESPN id, season, and week. A stat line wins over the roster."""

    def __init__(self) -> None:
        self.played: dict[tuple[int, int, int], str] = {}
        self.roster: dict[tuple[int, int, int], set[str]] = {}

    def _direct(self, espn_id: int, season: int, week: int) -> str | None:
        key = (int(espn_id), int(season), int(week))
        played = self.played.get(key)
        if played:
            return played
        teams = self.roster.get(key) or set()
        if len(teams) == 1:
            return next(iter(teams))
        return None

    def for_week(self, espn_id: int, season: int, week: int) -> str | None:
        """The club for that week, including a bye that the weekly file skipped.

        A stat line wins, then the only roster team. A missing week uses the
        season's only club, or the club on both sides of the gap. A gap between
        two different clubs is left alone.
        """
        direct = self._direct(espn_id, season, week)
        if direct:
            return direct
        options = self._by_season().get((int(espn_id), int(season)), {})
        if not options:
            return None
        clubs = set(options.values())
        if len(clubs) == 1:
            return next(iter(clubs))
        earlier = [known for known in options if known < int(week)]
        later = [known for known in options if known > int(week)]
        if earlier and later and options[max(earlier)] == options[min(later)]:
            return options[max(earlier)]
        return None

    def _by_season(self) -> dict[tuple[int, int], dict[int, str]]:
        cached = getattr(self, "_seasons", None)
        if cached is not None:
            return cached
        grouped: dict[tuple[int, int], dict[int, str]] = {}
        for player_id, season, week in set(self.played) | set(self.roster):
            team = self._direct(player_id, season, week)
            if team:
                grouped.setdefault((player_id, season), {})[week] = team
        self._seasons = grouped
        return grouped

    def season_options(self, espn_id: int, season: int) -> dict[int, str]:
        """Weeks that resolve to one team. The caller decides which to keep."""
        return dict(self._by_season().get((int(espn_id), int(season)), {}))


def correct_player_weeks(rows: list[dict], teams: WeekTeams) -> list[tuple[dict, str | None, str]]:
    """Set nfl_team from that week's club when ESPN disagrees. Defenses stay put."""
    changes = []
    for row in rows:
        if is_defense(row.get("pos"), row.get("name")):
            continue
        player_id = row.get("player_id")
        if player_id is None:
            continue
        found = teams.for_week(int(player_id), int(row["season"]), int(row["week"]))
        if not found:
            continue
        current = espn_abbrev(row.get("nfl_team"))
        if current == found:
            continue
        changes.append((row, current, found))
        row["nfl_team"] = found
    return changes


def correct_season_teams(rows: list[dict], teams: WeekTeams) -> list[tuple[dict, str | None, str]]:
    """A season total keeps ESPN's team when he actually played for that club.

    Otherwise it uses the team from his latest week that year.
    """
    changes = []
    for row in rows:
        if is_defense(row.get("pos"), row.get("name")):
            continue
        player_id = row.get("player_id")
        if player_id is None:
            continue
        options = teams.season_options(int(player_id), int(row["season"]))
        if not options:
            continue
        unique = set(options.values())
        current = espn_abbrev(row.get("nfl_team"))
        if current in unique:
            continue
        latest = options[max(options)]
        changes.append((row, current, latest))
        row["nfl_team"] = latest
    return changes


def season_team_lists(rows: list[dict]) -> dict[tuple[str, int], list[str]]:
    """Teams in the order they first appear, for players who have week rows."""
    ordered: dict[tuple[str, int], list[str]] = {}
    ranked = sorted(rows, key=lambda row: (row.get("name") or "", int(row["season"]), int(row["week"])))
    for row in ranked:
        team = espn_abbrev(row.get("nfl_team"))
        if not team or is_defense(row.get("pos"), row.get("name")):
            continue
        key = (str(row.get("name") or ""), int(row["season"]))
        seen = ordered.setdefault(key, [])
        if team not in seen:
            seen.append(team)
    return ordered


def align_record_seasons(players: dict[str, dict], week_rows: list[dict]) -> list[str]:
    """Drop an NFL club from a player-record season when he was not on it.

    A stored list that is only a subset of the real clubs is left alone.
    """
    derived = season_team_lists(week_rows)
    changed = []
    for name, rec in players.items():
        seasons = rec.get("seasons") or {}
        touched = False
        for year, acc in seasons.items():
            real = derived.get((name, int(year)))
            if not real:
                continue
            stored = [espn_abbrev(team) for team in (acc.get("nfl") or [])]
            stored = [team for team in stored if team]
            if not stored or set(stored) <= set(real):
                continue
            acc["nfl"] = list(real)
            touched = True
        if not touched:
            continue
        career: list[str] = []
        for year in sorted(seasons, key=lambda value: int(value)):
            for team in seasons[year].get("nfl") or []:
                if not career or career[-1] != team:
                    career.append(team)
        rec["teams"] = career
        changed.append(name)
    return changed


def _download(url: str, name: str) -> bytes | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "commissioner-report"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        print(f"  skip {name}: {exc}")
        return None
    path.write_bytes(data)
    return data


def _rows(url: str, name: str, fields: list[str]) -> list[dict]:
    raw = _download(url, name)
    if not raw:
        return []
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    kept = []
    for row in reader:
        kept.append({field: row.get(field) for field in fields})
    return kept


def load_week_teams(years: list[int]) -> WeekTeams:
    teams = WeekTeams()
    gsis_to_espn: dict[str, int] = {}
    for year in years:
        roster_rows = _rows(
            ROSTER_URL.format(year=year),
            f"roster_weekly_{year}.csv",
            ["season", "week", "team", "espn_id", "gsis_id", "game_type"],
        )
        for row in roster_rows:
            if (row.get("game_type") or "REG") != "REG":
                continue
            espn_id = _espn_id(row.get("espn_id"))
            gsis = (row.get("gsis_id") or "").strip()
            week = _week(row.get("week"))
            team = espn_abbrev(row.get("team"))
            if espn_id and gsis:
                gsis_to_espn[gsis] = espn_id
            if espn_id and week is not None and team:
                teams.roster.setdefault((espn_id, int(year), week), set()).add(team)
        stat_rows = _rows(
            STATS_URL.format(year=year),
            f"stats_player_week_{year}.csv",
            ["player_id", "season", "week", "team", "season_type"],
        )
        for row in stat_rows:
            if (row.get("season_type") or "REG") != "REG":
                continue
            espn_id = gsis_to_espn.get((row.get("player_id") or "").strip())
            week = _week(row.get("week"))
            team = espn_abbrev(row.get("team"))
            if espn_id and week is not None and team:
                teams.played[(espn_id, int(year), week)] = team
        print(f"  nfl teams {year}: {len(roster_rows)} roster rows")
    return teams


def self_test() -> None:
    teams = WeekTeams()
    teams.played[(1, 2023, 7)] = "CHI"
    teams.roster[(1, 2023, 7)] = {"CHI"}
    teams.roster[(2, 2023, 7)] = {"SF"}
    teams.roster[(3, 2023, 1)] = {"CHI", "CLE"}
    teams.roster[(6, 2023, 4)] = {"CHI"}
    teams.played[(7, 2023, 8)] = "CHI"
    teams.roster[(7, 2023, 8)] = {"CLE"}
    teams.roster[(8, 2023, 6)] = {"CHI"}
    teams.roster[(8, 2023, 8)] = {"CHI"}
    teams.roster[(9, 2023, 6)] = {"CHI"}
    teams.roster[(9, 2023, 8)] = {"CLE"}
    teams.roster[(10, 2023, 1)] = {"CHI"}
    teams.roster[(10, 2023, 3)] = {"CHI"}
    teams.roster[(10, 2023, 5)] = {"CLE"}
    rows = [
        {"player_id": 1, "season": 2023, "week": 7, "name": "D'Onta Foreman", "pos": "RB", "nfl_team": "CLE"},
        {"player_id": 2, "season": 2023, "week": 7, "name": "Stay", "pos": "WR", "nfl_team": "SF"},
        {"player_id": 3, "season": 2023, "week": 1, "name": "Split", "pos": "RB", "nfl_team": "CLE"},
        {"player_id": 4, "season": 2023, "week": 7, "name": "Browns D/ST", "pos": "D/ST", "nfl_team": "CLE"},
        {"player_id": 5, "season": 2023, "week": 7, "name": "Ghost", "pos": "WR", "nfl_team": "DAL"},
        {"player_id": 6, "season": 2023, "week": 4, "name": "Inactive", "pos": "RB", "nfl_team": "CLE"},
        {"player_id": 7, "season": 2023, "week": 8, "name": "Played", "pos": "RB", "nfl_team": "CLE"},
        {"player_id": 8, "season": 2023, "week": 7, "name": "Bye", "pos": "RB", "nfl_team": "CLE"},
        {"player_id": 9, "season": 2023, "week": 7, "name": "Trade", "pos": "RB", "nfl_team": "CLE"},
        {"player_id": 10, "season": 2023, "week": 2, "name": "Between", "pos": "RB", "nfl_team": "CLE"},
    ]
    changes = correct_player_weeks(rows, teams)
    assert [row["nfl_team"] for row in rows] == [
        "CHI", "SF", "CLE", "CLE", "DAL", "CHI", "CHI", "CHI", "CLE", "CHI",
    ]
    assert [(row["name"], old, new) for row, old, new in changes] == [
        ("D'Onta Foreman", "CLE", "CHI"),
        ("Inactive", "CLE", "CHI"),
        ("Played", "CLE", "CHI"),
        ("Bye", "CLE", "CHI"),
        ("Between", "CLE", "CHI"),
    ]
    seasons = [
        {"player_id": 1, "season": 2023, "name": "D'Onta Foreman", "pos": "RB", "nfl_team": "CLE"},
        {"player_id": 2, "season": 2023, "name": "Stay", "pos": "WR", "nfl_team": "SF"},
    ]
    season_changes = correct_season_teams(seasons, teams)
    assert seasons[0]["nfl_team"] == "CHI"
    assert seasons[1]["nfl_team"] == "SF"
    assert len(season_changes) == 1
    records = {
        "D'Onta Foreman": {
            "teams": ["CLE"],
            "seasons": {2023: {"nfl": ["CLE"]}, 2024: {"nfl": ["CLE"]}},
        }
    }
    weeks = [
        {"name": "D'Onta Foreman", "season": 2023, "week": 7, "pos": "RB", "nfl_team": "CHI"},
        {"name": "D'Onta Foreman", "season": 2024, "week": 1, "pos": "RB", "nfl_team": "CLE"},
    ]
    assert align_record_seasons(records, weeks) == ["D'Onta Foreman"]
    assert records["D'Onta Foreman"]["seasons"][2023]["nfl"] == ["CHI"]
    assert records["D'Onta Foreman"]["seasons"][2024]["nfl"] == ["CLE"]
    assert records["D'Onta Foreman"]["teams"] == ["CHI", "CLE"]
    assert espn_abbrev("LA") == "LAR"
    assert espn_abbrev("WAS") == "WSH"
    assert espn_abbrev("CHI") == "CHI"
    print("nfl teams ok")


if __name__ == "__main__":
    self_test()
