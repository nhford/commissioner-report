"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  chord as d3Chord,
  ribbon as d3Ribbon,
  type ChordGroup,
  type ChordSubgroup,
} from "d3-chord";
import { arc as d3Arc } from "d3-shape";
import { ownerColor } from "@/lib/trades";

type Hover =
  | { kind: "group"; index: number }
  | { kind: "ribbon"; source: number; target: number }
  | null;

type Props = {
  owners: string[];
  matrix: number[][];
};

function truncateName(name: string, max = 12) {
  if (name.length <= max) return name;
  return `${name.slice(0, max - 1)}…`;
}

function ribbonPath(source: ChordSubgroup, target: ChordSubgroup, radius: number) {
  const generator = d3Ribbon<unknown, ChordSubgroup>().radius(radius);
  return generator({ source, target }) as unknown as string | null;
}

export default function TradeChord({ owners, matrix }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<Hover>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width ?? 640;
      setWidth(Math.max(280, next));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const size = Math.min(width, 720);
  const pad = size < 400 ? 56 : 80;
  const outerRadius = Math.max(40, size / 2 - pad);
  const innerRadius = outerRadius * 0.92;

  const layout = useMemo(() => {
    if (!owners.length) return { groups: [], ribbons: [] };
    const layoutFn = d3Chord()
      .padAngle(0.04)
      .sortSubgroups((a: number, b: number) => b - a);
    const chords = layoutFn(matrix);
    return { groups: [...chords.groups], ribbons: [...chords] };
  }, [matrix, owners.length]);

  const arc = useMemo(
    () => d3Arc<ChordGroup>().innerRadius(innerRadius).outerRadius(outerRadius),
    [innerRadius, outerRadius],
  );

  const tooltip = useMemo(() => {
    if (!hover) return null;
    if (hover.kind === "group") {
      const name = owners[hover.index];
      const total = matrix[hover.index]?.reduce((sum, n) => sum + n, 0) ?? 0;
      return `${name} · ${total} trade${total === 1 ? "" : "s"}`;
    }
    const a = owners[hover.source];
    const b = owners[hover.target];
    const count = matrix[hover.source]?.[hover.target] ?? 0;
    return `${a} ↔ ${b} · ${count} trade${count === 1 ? "" : "s"}`;
  }, [hover, matrix, owners]);

  if (!owners.length) {
    return (
      <p className="px-4 py-10 text-center text-sm text-neutral-600">
        No completed trades in this view.
      </p>
    );
  }

  return (
    <div ref={wrapRef} className="relative w-full">
      <svg
        role="img"
        aria-label="Chord diagram of trades between owners"
        viewBox={`0 0 ${size} ${size}`}
        width="100%"
        height={size}
        className="mx-auto block max-w-full"
      >
        <g transform={`translate(${size / 2},${size / 2})`}>
          {layout.ribbons.map((ribbon) => {
            const source = ribbon.source.index;
            const target = ribbon.target.index;
            const active =
              hover == null ||
              (hover.kind === "ribbon" &&
                ((hover.source === source && hover.target === target) ||
                  (hover.source === target && hover.target === source))) ||
              (hover.kind === "group" &&
                (hover.index === source || hover.index === target));
            const d = ribbonPath(ribbon.source, ribbon.target, innerRadius);
            if (!d) return null;
            return (
              <path
                key={`ribbon-${source}-${target}`}
                d={d}
                fill={ownerColor(owners[source])}
                fillOpacity={active ? 0.72 : 0.08}
                stroke={ownerColor(owners[source])}
                strokeOpacity={active ? 0.35 : 0.05}
                className="cursor-pointer transition-opacity"
                onMouseEnter={() => setHover({ kind: "ribbon", source, target })}
                onMouseLeave={() => setHover(null)}
              />
            );
          })}
          {layout.groups.map((group) => {
            const d = arc(group);
            if (!d) return null;
            const mid = (group.startAngle + group.endAngle) / 2;
            const degrees = (mid * 180) / Math.PI - 90;
            const flip = degrees > 90 || degrees < -90;
            const labelR = outerRadius + 14;
            const x = Math.cos(mid - Math.PI / 2) * labelR;
            const y = Math.sin(mid - Math.PI / 2) * labelR;
            const active =
              hover == null ||
              (hover.kind === "group" && hover.index === group.index) ||
              (hover.kind === "ribbon" &&
                (hover.source === group.index || hover.target === group.index));
            return (
              <g key={`group-${group.index}`}>
                <path
                  d={d}
                  fill={ownerColor(owners[group.index])}
                  fillOpacity={active ? 1 : 0.25}
                  className="cursor-pointer"
                  onMouseEnter={() => setHover({ kind: "group", index: group.index })}
                  onMouseLeave={() => setHover(null)}
                />
                <text
                  x={x}
                  y={y}
                  dy="0.35em"
                  textAnchor={flip ? "end" : "start"}
                  transform={`rotate(${flip ? degrees + 180 : degrees} ${x} ${y})`}
                  className="fill-neutral-800"
                  style={{ fontSize: size < 400 ? 10 : 12 }}
                  opacity={active ? 1 : 0.35}
                  onMouseEnter={() => setHover({ kind: "group", index: group.index })}
                  onMouseLeave={() => setHover(null)}
                >
                  {truncateName(owners[group.index], size < 400 ? 9 : 14)}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      {tooltip ? (
        <p className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded bg-neutral-900 px-3 py-1 text-xs font-medium text-white shadow">
          {tooltip}
        </p>
      ) : null}
    </div>
  );
}
