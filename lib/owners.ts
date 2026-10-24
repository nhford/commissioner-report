import league from "@/data/league.json";

// Jack's full name is Jack Blatt. The site refers to him as Jack.

function namesFromBlock(block: Record<string, string> | undefined) {
  if (!block) return [];
  return Object.values(block).filter((name) => name && name !== "N/A");
}

export function activeOwners() {
  const year = String(league.current_season) as keyof typeof league.owners_by_year;
  return [...new Set(namesFromBlock(league.owners_by_year[year]))].sort((a, b) =>
    a.localeCompare(b),
  );
}

export function allOwners() {
  const names = new Set<string>();
  for (const block of Object.values(league.owners_by_year)) {
    for (const name of namesFromBlock(block)) names.add(name);
  }
  return [...names].sort((a, b) => a.localeCompare(b));
}

/** Owners who held a team in at least one season of this inclusive range. */
export function ownersBetween(fromYear: number, toYear: number) {
  const names = new Set<string>();
  for (const [year, block] of Object.entries(league.owners_by_year)) {
    const season = Number(year);
    if (season < fromYear || season > toYear) continue;
    for (const name of namesFromBlock(block)) names.add(name);
  }
  return [...names].sort((a, b) => a.localeCompare(b));
}
