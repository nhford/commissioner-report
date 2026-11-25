export type Feature = {
  href: string;
  label: string;
  blurb: string;
  soon?: boolean;
  /** Phone banner. Desktop lists every section. */
  banner?: boolean;
  /** Included in the post-scrape cache refresh. */
  revalidate?: boolean;
  /** reports.id for the home-page stamp. */
  reportId?: string;
};

export const FEATURES: Feature[] = [
  {
    href: "/median-monday",
    label: "Median Watch",
    blurb: "Chance to beat the league median and share of the top-scorer payout.",
    banner: true,
    revalidate: true,
    reportId: "median-monday",
  },
  {
    href: "/superlatives",
    label: "Superlatives",
    blurb: "All-time and current-season highs and lows for players and teams.",
    banner: true,
    revalidate: true,
    reportId: "superlatives",
  },
  {
    href: "/player-records",
    label: "Player Records",
    blurb: "Career win-loss for every player rostered in this league.",
    revalidate: true,
    reportId: "player-records",
  },
  {
    href: "/o-gami",
    label: "O-Gami",
    blurb: "Who has traded, played, or met in the playoffs: a grid of owner pairs.",
    revalidate: true,
    reportId: "trade-o-gami",
  },
  {
    href: "/sams-stuff",
    label: "Sam's Stuff",
    blurb: "Start/sit accuracy and all-play expected record for each season.",
    banner: true,
    revalidate: true,
  },
  {
    href: "/immaculate-grid",
    label: "Immaculate Grid",
    blurb: "A daily 3×3. Name a player who fits the row and the column.",
    soon: true,
    revalidate: true,
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

export const REVALIDATE_PATHS = [
  "/",
  ...FEATURES.filter((feature) => feature.revalidate).map((feature) => feature.href),
];
