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

