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
    label: "Median Monday",
    blurb: "Chance to beat the league median and share of the top-scorer payout.",
  },
  {
    href: "/player-records",
    label: "Player Records",
    blurb: "Career win-loss for every player rostered in this league.",
    soon: true,
  },
  {
    href: "/trade-o-gami",
    label: "Trade-o-gami",
    blurb: "Who trades with whom: a chord of completed deals between owners.",
    soon: true,
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
