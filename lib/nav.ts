export type NavItem = {
  href: string;
  label: string;
  soon?: boolean;
};

type Section = NavItem & {
  blurb: string;
};

const SECTIONS: Section[] = [
  {
    href: "/median-monday",
    label: "Median Watch",
    blurb: "Chance to beat the league median and share of the top-scorer payout.",
  },
  {
    href: "/superlatives",
    label: "Superlatives",
    blurb: "All-time and current-season highs and lows for players and teams.",
  },
  {
    href: "/player-records",
    label: "Player Records",
    blurb: "Career win-loss for every player rostered in this league.",
  },
  {
    href: "/o-gami",
    label: "O-Gami",
    blurb: "Who has traded, played, or met in the playoffs: a grid of owner pairs.",
  },
  {
    href: "/sams-stuff",
    label: "Sam's Stuff",
    blurb: "Start/sit accuracy and all-play expected record for each season.",
  },
  {
    href: "/lineup-efficiency",
    label: "Lineup Efficiency",
    blurb: "Actual lineup vs projection-optimal and best-possible.",
    soon: true,
  },
  {
    href: "/waiver-bids",
    label: "Waiver Bids",
    blurb: "FAAB spending, most-bid players, remaining budgets.",
    soon: true,
  },
  {
    href: "/draft-history",
    label: "Draft History",
    blurb: "Auction bids, values, and overpay by season.",
    soon: true,
  },
];

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home" },
  ...SECTIONS.map(({ href, label, soon }) => ({ href, label, soon })),
];

/** Phone banner. Desktop uses the full sidebar list. */
export const BANNER_ITEMS: NavItem[] = [
  { href: "/", label: "Home" },
  { href: "/median-monday", label: "Median Watch" },
  { href: "/superlatives", label: "Superlatives" },
  { href: "/sams-stuff", label: "Sam's Stuff" },
];

export const HUB_CARDS = SECTIONS.map(({ href, label, blurb, soon }) => ({
  href,
  title: label,
  blurb,
  soon,
}));

export function isActivePath(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
