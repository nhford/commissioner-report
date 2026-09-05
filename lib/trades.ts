export type TradeRow = {
  id: string;
  season: number;
  week: number;
  owners: string[];
};

export type TradePair = {
  a: string;
  b: string;
  count: number;
};

function pairKey(a: string, b: string): [string, string] {
  return a < b ? [a, b] : [b, a];
}

export function countPairs(trades: TradeRow[], ownerSet: Set<string>): TradePair[] {
  const counts = new Map<string, number>();
  for (const trade of trades) {
    const involved = [...new Set(trade.owners)].filter((name) => ownerSet.has(name));
    if (involved.length < 2) continue;
    for (let i = 0; i < involved.length; i++) {
      for (let j = i + 1; j < involved.length; j++) {
        const [a, b] = pairKey(involved[i], involved[j]);
        const key = `${a}\0${b}`;
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
    }
  }
  return [...counts.entries()]
    .map(([key, count]) => {
      const [a, b] = key.split("\0");
      return { a, b, count };
    })
    .sort((left, right) => {
      if (right.count !== left.count) return right.count - left.count;
      return `${left.a}${left.b}`.localeCompare(`${right.a}${right.b}`);
    });
}

export function ownersInPairs(pairs: TradePair[]) {
  const names = new Set<string>();
  for (const pair of pairs) {
    names.add(pair.a);
    names.add(pair.b);
  }
  return [...names].sort((a, b) => a.localeCompare(b));
}

export function chordMatrix(owners: string[], pairs: TradePair[]) {
  const index = new Map(owners.map((name, i) => [name, i]));
  const matrix = owners.map(() => owners.map(() => 0));
  for (const pair of pairs) {
    const i = index.get(pair.a);
    const j = index.get(pair.b);
    if (i == null || j == null) continue;
    matrix[i][j] = pair.count;
    matrix[j][i] = pair.count;
  }
  return matrix;
}

export const OWNER_COLORS: Record<string, string> = {
  Noah: "#2563eb",
  Liam: "#059669",
  Gandhari: "#d97706",
  Alex: "#dc2626",
  Ajay: "#7c3aed",
  Stephen: "#0891b2",
  Rikhav: "#db2777",
  Divi: "#65a30d",
  Dean: "#ea580c",
  Raymond: "#4f46e5",
  Keshav: "#0d9488",
  Sam: "#be123c",
  Jack: "#ca8a04",
  Kyler: "#57534e",
  Andoni: "#9333ea",
};

const FALLBACK_COLORS = [
  "#1f77b4",
  "#ff7f0e",
  "#2ca02c",
  "#d62728",
  "#9467bd",
  "#8c564b",
  "#e377c2",
  "#7f7f7f",
  "#bcbd22",
  "#17becf",
];

export function ownerColor(name: string) {
  if (OWNER_COLORS[name]) return OWNER_COLORS[name];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  return FALLBACK_COLORS[hash % FALLBACK_COLORS.length];
}
