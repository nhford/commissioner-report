"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import TeamLogo from "@/components/TeamLogo";
import {
  type Board,
  type GridGuess,
  type GridHeader,
  type SearchHit,
  formatGridDate,
  formatPercent,
  formatScore,
  isUuid,
  rarityClass,
  searchNeedle,
} from "@/lib/grid";

const ANON_KEY = "cr-grid-anon";
let memoryAnon: string | null = null;

function subscribeAnon() {
  return () => {};
}

function readAnon() {
  if (memoryAnon) return memoryAnon;
  let id = localStorage.getItem(ANON_KEY);
  if (!id || !isUuid(id)) {
    id = crypto.randomUUID();
    localStorage.setItem(ANON_KEY, id);
  }
  memoryAnon = id;
  return id;
}

function emptyAnon() {
  return null;
}

function correctAt(guesses: GridGuess[], cell: number) {
  return guesses.find((guess) => guess.cell === cell && guess.correct) ?? null;
}

function nextEmpty(board: Board, after: number) {
  for (let step = 1; step <= 9; step += 1) {
    const cell = (after + step) % 9;
    if (!correctAt(board.guesses, cell)) return cell;
  }
  return null;
}

function HeaderCell({ header }: { header: GridHeader }) {
  if (header.logo) {
    return (
      <div
        title={header.detail}
        className="flex min-h-16 items-center justify-center rounded-md bg-neutral-200 px-1 sm:min-h-24"
      >
        <TeamLogo src={header.logo} alt={header.detail} size="md" />
      </div>
    );
  }
  return (
    <div
      title={header.detail}
      className="flex min-h-16 flex-col items-center justify-center rounded-md bg-neutral-200 px-1 text-center text-[11px] font-semibold leading-tight text-neutral-800 sm:min-h-24 sm:text-xs"
    >
      <span>{header.label}</span>
      {header.line2 ? <span>{header.line2}</span> : null}
    </div>
  );
}

export default function ImmaculateGrid() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requested = searchParams.get("date");
  const anon = useSyncExternalStore(subscribeAnon, readAnon, emptyAnon);
  const [board, setBoard] = useState<Board | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [flash, setFlash] = useState<number | null>(null);
  const [confirmGiveUp, setConfirmGiveUp] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const searchRequest = useRef(0);

  useEffect(() => {
    if (!anon) return;
    const controller = new AbortController();
    const params = new URLSearchParams({ anonId: anon });
    if (requested) params.set("date", requested);
    fetch(`/api/grid?${params}`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "Could not load the grid.");
        setBoard(body as Board);
      })
      .catch((err: Error) => {
        if (err.name === "AbortError") return;
        setError(err.message || "Could not load the grid.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [anon, requested, attempt]);

  useEffect(() => {
    if (flash == null) return;
    const id = window.setTimeout(() => setFlash(null), 700);
    return () => window.clearTimeout(id);
  }, [flash]);

  useEffect(() => {
    const current = stripRef.current?.querySelector<HTMLElement>("[aria-current='date']");
    current?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [board?.date]);

  useEffect(() => {
    if (active == null) return;
    inputRef.current?.focus();
  }, [active, board?.date]);

  useEffect(() => {
    const needle = searchNeedle(query);
    const requestId = searchRequest.current + 1;
    searchRequest.current = requestId;
    if (needle.length < 2) return;
    const handle = window.setTimeout(() => {
      fetch(`/api/grid/search?q=${encodeURIComponent(query)}`, { cache: "no-store" })
        .then(async (response) => {
          const body = await response.json();
          if (!response.ok) throw new Error(body.error || "Search failed.");
          return body.players as SearchHit[];
        })
        .then((players) => {
          if (searchRequest.current === requestId) setHits(players);
        })
        .catch(() => {
          if (searchRequest.current === requestId) setHits([]);
        })
        .finally(() => {
          if (searchRequest.current === requestId) setSearching(false);
        });
    }, 150);
    return () => window.clearTimeout(handle);
  }, [query]);

  function openDate(date: string) {
    if (!board || date === board.date) return;
    setLoading(true);
    setBoard(null);
    setActive(null);
    setQuery("");
    setHits([]);
    setMessage(null);
    setConfirmGiveUp(false);
    setError(null);
    const path = date === board.today ? "/immaculate-grid" : `/immaculate-grid?date=${date}`;
    router.replace(path, { scroll: false });
  }

  function selectCell(cell: number) {
    if (!board || board.finished || pending || correctAt(board.guesses, cell)) return;
    setActive(cell);
    setQuery("");
    setHits([]);
    setMessage(null);
    setConfirmGiveUp(false);
  }

  async function submit(playerId: string) {
    if (!board?.date || !anon || active == null || pending) return;
    setPending(true);
    setMessage(null);
    try {
      const response = await fetch("/api/grid/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date: board.date,
          anonId: anon,
          cell: active,
          playerId,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "That guess did not save.");
      const next = body.board as Board;
      setBoard(next);
      setQuery("");
      setHits([]);
      if (body.duplicate) {
        setMessage("Already tried.");
        return;
      }
      if (!body.correct) {
        setFlash(active);
        setMessage("Not a match.");
        return;
      }
      setMessage(null);
      setActive(next.finished ? null : nextEmpty(next, active));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "That guess did not save.");
    } finally {
      setPending(false);
    }
  }

  async function giveUp() {
    if (!board?.date || !anon || pending) return;
    setPending(true);
    setMessage(null);
    try {
      const response = await fetch("/api/grid/give-up", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: board.date, anonId: anon }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not end the grid.");
      setBoard(body.board as Board);
      setActive(null);
      setConfirmGiveUp(false);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not end the grid.");
    } finally {
      setPending(false);
    }
  }

  if (loading && !board) {
    return <p className="mt-8 text-sm text-white/60">Loading the grid…</p>;
  }

  if (error && !board) {
    return (
      <div className="mt-8">
        <p className="text-sm text-white/70">{error}</p>
        <button
          type="button"
          onClick={() => {
            setLoading(true);
            setError(null);
            setAttempt((value) => value + 1);
          }}
          className="mt-3 text-sm text-white underline decoration-emerald-400 underline-offset-2"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!board) return null;

  if (!board.playable) {
    const when = board.nextDrop
      ? formatGridDate(board.nextDrop, { weekday: "long", month: "long", day: "numeric" })
      : null;
    return (
      <p className="mt-8 max-w-xl text-sm text-white/70">
        {when ? `The next grid drops on ${when}.` : "The next grid has not been scheduled."}
      </p>
    );
  }

  const activeHeader =
    active == null
      ? null
      : {
          row: board.rows[Math.floor(active / 3)],
          col: board.cols[active % 3],
        };
  const misses =
    active == null
      ? []
      : board.guesses.filter((guess) => guess.cell === active && !guess.correct);
  const filled = board.guesses.filter((guess) => guess.correct).length;
  const needle = searchNeedle(query);
  const visibleHits = needle.length < 2 ? [] : hits;
  const visibleSearching = needle.length >= 2 && searching;

  return (
    <div className={active != null && !board.finished ? "pb-44" : ""}>
      {board.archive.length > 0 ? (
        <div
          ref={stripRef}
          className="mt-6 flex max-w-xl gap-1 overflow-x-auto pb-1"
          aria-label="Past grids"
        >
          {board.archive.map((day) => {
            const selected = day.date === board.date;
            return (
              <button
                key={day.date}
                type="button"
                aria-current={selected ? "date" : undefined}
                onClick={() => openDate(day.date)}
                className={`shrink-0 rounded-md px-2 py-1 text-xs ${
                  selected
                    ? "bg-white/15 font-semibold text-white"
                    : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
              >
                <span className="block">
                  {day.date === board.today
                    ? "Today"
                    : formatGridDate(day.date, { month: "short", day: "numeric" })}
                </span>
                <span
                  className={`mx-auto mt-1 block h-1 w-1 rounded-full ${
                    day.finished ? "bg-emerald-400" : "bg-transparent"
                  }`}
                />
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="mt-4 flex max-w-xl items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            {board.date
              ? formatGridDate(board.date, {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                })
              : "Immaculate Grid"}
          </h2>
          {board.offseason && board.nextDrop ? (
            <p className="mt-1 text-sm text-white/60">
              This season’s grids are still open. The next one drops on{" "}
              {formatGridDate(board.nextDrop, {
                weekday: "long",
                month: "long",
                day: "numeric",
              })}
              .
            </p>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex max-w-xl items-center justify-between gap-3">
        {board.finished ? (
          <p className="text-sm text-white/80">
            <span className="font-semibold text-white">{filled}</span> of 9 squares
          </p>
        ) : (
          <p className="text-sm text-white/80">
            <span className="font-semibold text-white">{board.guessesLeft}</span>{" "}
            {board.guessesLeft === 1 ? "guess left" : "guesses left"}
          </p>
        )}
        {board.finished ? null : confirmGiveUp ? (
          <div className="flex items-center gap-3 text-sm">
            <button
              type="button"
              onClick={giveUp}
              disabled={pending}
              className="text-white underline decoration-emerald-400 underline-offset-2 disabled:opacity-50"
            >
              End it
            </button>
            <button
              type="button"
              onClick={() => setConfirmGiveUp(false)}
              className="text-white/60 hover:text-white"
            >
              Keep playing
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmGiveUp(true)}
            disabled={pending}
            className="text-sm text-white/70 underline decoration-white/30 underline-offset-2 hover:text-white disabled:opacity-50"
          >
            Give up
          </button>
        )}
      </div>

      <div
        className="mt-3 grid max-w-xl gap-1"
        style={{ gridTemplateColumns: "minmax(3.25rem, 4.5rem) repeat(3, minmax(0, 1fr))" }}
        aria-label="Immaculate Grid"
      >
        <div />
        {board.cols.map((header) => (
          <HeaderCell key={`col-${header.detail}`} header={header} />
        ))}
        {board.rows.flatMap((row, rowIndex) => [
            <HeaderCell key={`row-${row.detail}`} header={row} />,
            ...board.cols.map((col, colIndex) => {
              const cell = rowIndex * 3 + colIndex;
              const correct = correctAt(board.guesses, cell);
              const result = board.results?.cells[cell] ?? null;
              const label = `${row.detail}. ${col.detail}.`;
              const shared = `flex min-h-16 flex-col items-center justify-center rounded-md px-1 text-center ring-offset-2 ring-offset-neutral-800 sm:min-h-24 ${
                flash === cell ? "bg-red-100" : "bg-white"
              }`;
              if (correct) {
                return (
                  <div key={cell} className={`${shared} text-neutral-900`} aria-label={`${label} ${correct.name}`}>
                    <span className="text-[11px] font-semibold leading-tight break-words sm:text-sm">
                      {correct.name}
                    </span>
                    <span className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-neutral-500">
                      {correct.pos}
                    </span>
                    {result ? (
                      <span className={`mt-1 text-[10px] font-semibold sm:text-xs ${rarityClass(result.percent)}`}>
                        {formatPercent(result.percent, result.estimated)}
                      </span>
                    ) : null}
                  </div>
                );
              }
              if (board.finished) {
                return (
                  <div
                    key={cell}
                    className={`${shared} text-neutral-300`}
                    aria-label={`${label} Missed.`}
                  />
                );
              }
              const selected = active === cell;
              return (
                <button
                  key={cell}
                  type="button"
                  aria-label={label}
                  aria-pressed={selected}
                  disabled={pending}
                  onClick={() => selectCell(cell)}
                  className={`${shared} text-neutral-900 hover:bg-emerald-50 disabled:opacity-70 ${
                    selected ? "ring-2 ring-emerald-500" : ""
                  }`}
                />
              );
            }),
          ])}
      </div>

      {board.finished && board.results ? (
        <div className="mt-4 max-w-xl">
          <p className="text-lg font-semibold">Rarity score {formatScore(board.results.score)}</p>
          <p className="mt-1 text-sm text-white/65">
            Lower is rarer. Each missed square counts as 100.
          </p>
          {board.results.others === 0 ? (
            <p className="mt-2 text-sm text-white/65">
              No one else has played this grid, so these percents are estimates.
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 max-w-xl text-sm text-white/60">Tap a square, then search for a player.</p>
      )}

      <details className="mt-4 max-w-xl text-sm text-white/65">
        <summary className="cursor-pointer text-white/75">How answers are counted</summary>
        <p className="mt-2">
          Name a player who fits both headers. Nine guesses cover the whole grid. A right
          answer and a wrong answer each cost one. The same player can fill more than one
          square. Misses stay blank.
        </p>
        <p className="mt-2">
          Teams mean he played a regular-season or playoff game for that franchise. Raiders,
          Chargers, Rams, and Oilers count with the current club. Season finishes and
          single-game totals are regular-season PPR from 1999 through {board.throughSeason}.
          Points are nflverse PPR: one point per reception and four-point passing touchdowns,
          close to this league’s scoring.
        </p>
        <p className="mt-2">
          After you finish, each name shows how often it was picked. Until eight people fill
          a square, that percent is an estimate weighted by career scoring.
        </p>
      </details>

      {activeHeader && !board.finished ? (
        <form
          className="fixed inset-x-0 bottom-0 z-30 border-t border-white/15 bg-neutral-800 px-4 py-3 md:left-56"
          onSubmit={(event) => {
            event.preventDefault();
            if (visibleHits[0]) void submit(visibleHits[0].id);
          }}
        >
          <p className="text-xs text-white/55">
            {activeHeader.row.detail}. {activeHeader.col.detail}.
          </p>
          <label className="mt-2 block">
            <span className="sr-only">Search players</span>
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => {
                const next = event.target.value;
                setQuery(next);
                if (searchNeedle(next).length >= 2) setSearching(true);
                else setSearching(false);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") setActive(null);
              }}
              placeholder="Search players"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              disabled={pending}
              className="w-full rounded-md border border-white/20 bg-neutral-900 px-3 py-2 text-base text-white outline-none focus:border-emerald-400"
            />
          </label>
          {visibleSearching ? <p className="mt-2 text-xs text-white/50">Searching…</p> : null}
          {message ? (
            <p className="mt-2 text-sm text-white/80" aria-live="polite">
              {message}
            </p>
          ) : null}
          {misses.length > 0 ? (
            <p className="mt-2 text-xs text-white/50">
              Misses: {misses.map((guess) => guess.name).join(", ")}
            </p>
          ) : null}
          {visibleHits.length > 0 ? (
            <ul className="mt-2 max-h-40 overflow-y-auto" aria-label="Matching players">
              {visibleHits.map((player) => (
                <li key={player.id}>
                  <button
                    type="button"
                    onClick={() => void submit(player.id)}
                    disabled={pending}
                    className="flex w-full items-baseline gap-2 rounded px-2 py-2 text-left text-sm hover:bg-white/10 disabled:opacity-50"
                  >
                    <span className="font-medium">{player.name}</span>
                    <span className="text-white/50">
                      {player.pos} · {player.years}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {!visibleSearching && needle.length >= 2 && visibleHits.length === 0 ? (
            <p className="mt-2 text-xs text-white/50">No players found.</p>
          ) : null}
        </form>
      ) : null}
    </div>
  );
}
