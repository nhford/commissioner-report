"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import TradeChord from "./TradeChord";
import { gridOwners, ownerFullName, ownerInitials } from "@/lib/owners";
import {
  countMatrix,
  gamesPlayed,
  h2hMatrix,
  playoffMatrix,
  recordLabel,
  type OwnerGame,
  type RecordCell,
} from "@/lib/ogami";
import { countPairs, type TradeRow } from "@/lib/trades";

type Overlay = "trades" | "h2h" | "playoff";
type Roster = "current" | "all" | "colored" | "normal";
type TradeShape = "grid" | "spool";

type CountModel = {
  kind: "count";
  matrix: number[][];
  max: number;
  filled: boolean;
  label: (row: string, col: string, count: number) => string;
};

type H2HModel = {
  kind: "h2h";
  matrix: RecordCell[][];
  filled: boolean;
};

type Model = CountModel | H2HModel;

const HINT: Record<Overlay, string> = {
  trades: "Each number is completed trades between that pair, in both directions. Read a row or a column.",
  h2h: "Each cell is the row owner's record against the column owner. Regular season and winners-bracket games both count. Green is ahead for the row owner, red is behind.",
  playoff: "Each number is winners-bracket games between that pair, in both directions. Read a row or a column.",
};

const ROSTER_HINT: Record<Roster, string> = {
  current: "Current owners, alphabetical.",
  all: "Every owner, alphabetical.",
  colored: "Colored owners only. Inactive owners are left out.",
  normal: "Normal owners only. Inactive owners are left out.",
};

function mix(from: number, to: number, t: number) {
  return Math.round(from + (to - from) * t);
}

function countStyle(count: number, max: number) {
  const t = max > 0 ? count / max : 1;
  const v = mix(88, 245, t);
  return {
    backgroundColor: `rgb(${v} ${v} ${v})`,
    color: v > 160 ? "#171717" : "#ffffff",
  };
}

function recordStyle(cell: RecordCell) {
  const played = gamesPlayed(cell);
  const edge = played ? (cell.w - cell.l) / played : 0;
  const strength = Math.abs(edge);
  const toward = edge >= 0 ? [74, 222, 128] : [248, 113, 113];
  const r = mix(120, toward[0], strength);
  const g = mix(120, toward[1], strength);
  const b = mix(120, toward[2], strength);
  const light = r + g + b > 420;
  return {
    backgroundColor: `rgb(${r} ${g} ${b})`,
    color: light ? (edge >= 0 ? "#052e16" : "#450a0a") : "#ffffff",
  };
}

function maxUpper(matrix: number[][]) {
  let max = 0;
  for (let i = 0; i < matrix.length; i++) {
    for (let j = i + 1; j < matrix.length; j++) {
      if (matrix[i][j] > max) max = matrix[i][j];
    }
  }
  return max;
}

function countFilled(matrix: number[][]) {
  for (let i = 0; i < matrix.length; i++) {
    for (let j = i + 1; j < matrix.length; j++) {
      if (matrix[i][j] > 0) return true;
    }
  }
  return false;
}

function h2hFilled(matrix: RecordCell[][]) {
  for (let i = 0; i < matrix.length; i++) {
    for (let j = 0; j < matrix.length; j++) {
      if (i !== j && gamesPlayed(matrix[i][j]) > 0) return true;
    }
  }
  return false;
}

function tradeLabel(row: string, col: string, count: number) {
  return `${row} vs ${col} · ${count} ${count === 1 ? "trade" : "trades"}`;
}

function playoffLabel(row: string, col: string, count: number) {
  return `${row} vs ${col} · ${count} ${count === 1 ? "playoff game" : "playoff games"}`;
}

const SELECT_CLASS =
  "min-h-9 max-w-full rounded border border-white/70 bg-neutral-900 px-2 text-sm text-white";

function FieldSelect<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: { id: T; label: string }[];
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-white/70">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className={SELECT_CLASS}
      >
      {options.map((option) => (
        <option key={option.id} value={option.id} className="bg-neutral-900">
          {option.label}
        </option>
      ))}
      </select>
    </label>
  );
}

export default function TradeOgamiView({
  trades,
  games,
}: {
  trades: TradeRow[];
  games: OwnerGame[];
}) {
  const [overlay, setOverlay] = useState<Overlay>("trades");
  const [roster, setRoster] = useState<Roster>("current");
  const [tradeShape, setTradeShape] = useState<TradeShape>("spool");

  const owners = useMemo(() => gridOwners(roster), [roster]);

  const spool = useMemo(() => {
    const ownerSet = new Set(owners);
    const pairs = countPairs(trades, ownerSet);
    const involved = new Set<string>();
    for (const pair of pairs) {
      involved.add(pair.a);
      involved.add(pair.b);
    }
    const named = owners.filter((name) => involved.has(name));
    return { owners: named, matrix: countMatrix(named, pairs) };
  }, [owners, trades]);

  const model = useMemo<Model>(() => {
    const ownerSet = new Set(owners);
    if (overlay === "h2h") {
      const matrix = h2hMatrix(owners, games, ownerSet);
      return { kind: "h2h", matrix, filled: h2hFilled(matrix) };
    }
    if (overlay === "playoff") {
      const matrix = playoffMatrix(owners, games, ownerSet);
      return {
        kind: "count",
        matrix,
        max: maxUpper(matrix),
        filled: countFilled(matrix),
        label: playoffLabel,
      };
    }
    const matrix = countMatrix(owners, countPairs(trades, ownerSet));
    return {
      kind: "count",
      matrix,
      max: maxUpper(matrix),
      filled: countFilled(matrix),
      label: tradeLabel,
    };
  }, [games, overlay, owners, trades]);

  const cellClass =
    overlay === "h2h"
      ? "h-9 min-w-[3.25rem] rounded-sm px-0.5 text-center text-[0.65rem] tabular-nums"
      : "h-9 w-9 rounded-sm text-center text-xs tabular-nums";
  const showSpool = overlay === "trades" && tradeShape === "spool";
  const tableRef = useRef<HTMLTableElement>(null);
  const [tableBox, setTableBox] = useState({ width: 560, height: 520 });

  useEffect(() => {
    const table = tableRef.current;
    if (!table) return;
    const measure = () => {
      const rect = table.getBoundingClientRect();
      const width = Math.round(rect.width);
      const height = Math.round(rect.height);
      if (width < 40 || height < 40) return;
      setTableBox((prev) =>
        prev.width === width && prev.height === height ? prev : { width, height },
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(table);
    return () => observer.disconnect();
  }, [owners, overlay, cellClass]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <FieldSelect
          label="Content"
          value={overlay}
          onChange={setOverlay}
          options={[
            { id: "trades", label: "Trades" },
            { id: "h2h", label: "H2H" },
            { id: "playoff", label: "Playoff Match" },
          ]}
        />
        <FieldSelect
          label="Owners"
          value={roster}
          onChange={setRoster}
          options={[
            { id: "current", label: "Current" },
            { id: "all", label: "All historical" },
            { id: "colored", label: "Colored" },
            { id: "normal", label: "Normal" },
          ]}
        />
        {overlay === "trades" ? (
          <FieldSelect
            label="Style"
            value={tradeShape}
            onChange={setTradeShape}
            options={[
              { id: "grid", label: "Grid" },
              { id: "spool", label: "Spool" },
            ]}
          />
        ) : null}
      </div>
      <p className="max-w-2xl text-sm text-white/55">
        {ROSTER_HINT[roster]} {showSpool ? "Each ribbon is completed trades between two owners. Arc length is how often that owner is in a deal." : HINT[overlay]}
      </p>
      {!model.filled ? (
        <p className="text-sm text-white/55">Nothing recorded between these owners yet.</p>
      ) : null}

      {showSpool ? (
        <div className="max-w-2xl overflow-x-auto overscroll-x-contain">
          <TradeChord
            owners={spool.owners}
            matrix={spool.matrix}
            width={tableBox.width}
            height={tableBox.height}
          />
        </div>
      ) : null}
      <div
        className={
          showSpool
            ? "pointer-events-none invisible absolute left-0 top-0"
            : "overflow-x-auto overscroll-x-contain"
        }
        aria-hidden={showSpool}
      >
      <table ref={tableRef} className="border-separate border-spacing-1">
          <caption className="sr-only">
            {overlay === "trades"
              ? "Completed trades between owners"
              : overlay === "h2h"
                ? "Head-to-head records between owners"
                : "Winners-bracket games between owners"}
          </caption>
          <thead>
            <tr>
              <th className="sticky left-0 z-20 bg-[#262626]" scope="col" />
              {owners.map((name) => (
                <th
                  key={name}
                  scope="col"
                  aria-label={ownerFullName(name)}
                  title={ownerFullName(name)}
                  className="px-0.5 pb-1 text-center text-[0.65rem] font-medium text-white/70"
                >
                  {ownerInitials(name)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {owners.map((rowName, i) => (
              <tr key={rowName}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-[#262626] pr-2 text-left text-xs font-medium whitespace-nowrap"
                >
                  {rowName}
                </th>
                {owners.map((colName, j) => {
                  const hidden = i === j;
                  if (hidden) {
                    return <td key={colName} className={`${cellClass} bg-neutral-950`} />;
                  }
                  if (model.kind === "h2h") {
                    const cell = model.matrix[i][j];
                    if (gamesPlayed(cell) === 0) {
                      return <td key={colName} className={`${cellClass} bg-neutral-950`} />;
                    }
                    const label = `${rowName} vs ${colName} · ${recordLabel(cell)}`;
                    return (
                      <td
                        key={colName}
                        tabIndex={0}
                        aria-label={label}
                        title={label}
                        style={recordStyle(cell)}
                        className={`${cellClass} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-white`}
                      >
                        {recordLabel(cell)}
                      </td>
                    );
                  }
                  const count = model.matrix[i][j];
                  if (count <= 0) {
                    return <td key={colName} className={`${cellClass} bg-neutral-950`} />;
                  }
                  const label = model.label(rowName, colName, count);
                  return (
                    <td
                      key={colName}
                      tabIndex={0}
                      aria-label={label}
                      title={label}
                      style={countStyle(count, model.max)}
                      className={`${cellClass} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-white`}
                    >
                      {count}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
