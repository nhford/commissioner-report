import league from "@/data/league.json";

// The site refers to each owner by the name in owners_by_year.
// full_names holds the given name and surname. Jack is Jack Blatt.

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

/** Current-season owners in league team order. */
export function currentOwners() {
  const year = String(league.current_season) as keyof typeof league.owners_by_year;
  const block = league.owners_by_year[year];
  if (!block) return [];
  const seen = new Set<string>();
  const names: string[] = [];
  for (const id of Object.keys(block)
    .map((key) => Number(key))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b)) {
    const name = block[String(id) as keyof typeof block];
    if (!name || name === "N/A" || seen.has(name)) continue;
    seen.add(name);
    names.push(name);
  }
  return names;
}

/** Alphabetical owners for an O-Gami roster. Colored and Normal are active owners only. */
export function gridOwners(roster: "current" | "all" | "colored" | "normal") {
  if (roster === "all") return [...allOwners()].sort((a, b) => a.localeCompare(b));
  const active = new Set(currentOwners());
  if (roster === "current") {
    return [...active].sort((a, b) => a.localeCompare(b));
  }
  const listed = [...(league.owner_groups?.[roster] ?? [])] as string[];
  return listed
    .filter((name) => active.has(name))
    .sort((a, b) => a.localeCompare(b));
}

export function allOwners() {
  const names = new Set<string>();
  for (const block of Object.values(league.owners_by_year)) {
    for (const name of namesFromBlock(block)) names.add(name);
  }
  return [...names].sort((a, b) => a.localeCompare(b));
}

export function ownerFullName(name: string) {
  const full = league.full_names?.[name as keyof typeof league.full_names];
  return full || name;
}

/** First initial plus last initial, from the stored full name. */
export function ownerInitials(name: string) {
  const parts = ownerFullName(name).split(/\s+/).filter(Boolean);
  if (parts.length < 2) return (parts[0]?.[0] ?? name[0] ?? "").toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
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
