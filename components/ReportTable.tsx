"use client";

import { Fragment, useMemo, useState, type ReactNode } from "react";

export type SortDir = "asc" | "desc";

export type Column<T> = {
  key: string;
  label: string;
  natural: SortDir;
  align?: "left" | "center";
  numeric?: boolean;
  render: (row: T) => ReactNode;
  sortValue: (row: T) => string | number;
};

type Props<T> = {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  rowClassName?: (row: T) => string;
  defaultSort: { key: string; dir: SortDir };
  tableClassName?: string;
  renderExpanded?: (row: T) => ReactNode;
};

function sortIcon(active: boolean, dir: SortDir) {
  if (!active) return "";
  return dir === "desc" ? "↓" : "↑";
}

export default function ReportTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  rowClassName,
  defaultSort,
  tableClassName,
  renderExpanded,
}: Props<T>) {
  const [sorted, setSorted] = useState(defaultSort);
  const [openKey, setOpenKey] = useState<string | null>(null);

  const data = useMemo(() => {
    const col = columns.find((column) => column.key === sorted.key);
    if (!col) return rows;
    const sign = sorted.dir === "asc" ? -1 : 1;
    return [...rows].sort((a, b) => {
      const av = col.sortValue(a);
      const bv = col.sortValue(b);
      if (av < bv) return sign;
      if (av > bv) return -sign;
      return 0;
    });
  }, [columns, rows, sorted]);

  return (
    <div className="w-full overflow-x-auto">
      <table
        className={`w-full min-w-[32rem] table-fixed text-left bg-white text-black rounded-lg ${tableClassName ?? ""}`}
      >
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="text-sm md:text-base border-b border-neutral-300">
            {columns.map((col) => {
              const active = sorted.key === col.key;
              const ariaSort = active
                ? sorted.dir === "asc"
                  ? "ascending"
                  : "descending"
                : "none";
              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={ariaSort}
                  className={`px-2 py-3 whitespace-nowrap ${
                    col.align === "left" ? "text-left" : "text-center"
                  } ${active ? "bg-neutral-200" : ""}`}
                >
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 transition-colors hover:underline decoration-black underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-black"
                    onClick={() => {
                      const nextDir =
                        active && sorted.dir === col.natural
                          ? col.natural === "desc"
                            ? "asc"
                            : "desc"
                          : col.natural;
                      setSorted({ key: col.key, dir: nextDir });
                    }}
                  >
                    <span>{col.label}</span>
                    <span aria-hidden className="min-w-[0.75rem]">
                      {sortIcon(active, sorted.dir)}
                    </span>
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => {
            const key = rowKey(row);
            const expanded = Boolean(renderExpanded) && openKey === key;
            return (
              <Fragment key={key}>
                <tr
                  className={`border-b border-neutral-600 transition-colors hover:bg-neutral-100 ${
                    renderExpanded ? "cursor-pointer" : ""
                  } ${expanded ? "bg-neutral-100" : ""} ${
                    rowClassName?.(row) ?? ""
                  }`}
                  aria-expanded={renderExpanded ? expanded : undefined}
                  tabIndex={renderExpanded ? 0 : undefined}
                  onClick={
                    renderExpanded
                      ? () => setOpenKey(expanded ? null : key)
                      : undefined
                  }
                  onKeyDown={
                    renderExpanded
                      ? (event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setOpenKey(expanded ? null : key);
                          }
                        }
                      : undefined
                  }
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-2 py-3 ${
                        col.align === "left" ? "text-left" : "text-center"
                      } ${col.numeric ? "tabular-nums" : ""} ${
                        sorted.key === col.key ? "bg-neutral-200/70" : ""
                      }`}
                    >
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
                {expanded ? (
                  <tr className="border-b border-neutral-600">
                    <td colSpan={columns.length} className="px-3 py-3 bg-neutral-50">
                      {renderExpanded?.(row)}
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
