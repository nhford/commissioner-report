import league from "@/data/league.json";

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
