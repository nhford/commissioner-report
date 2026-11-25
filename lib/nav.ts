import { FEATURES, type Feature } from "@/lib/features";

export type NavItem = {
  href: string;
  label: string;
  soon?: boolean;
};

export type HubCard = Feature & {
  title: string;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home" },
  ...FEATURES.map(({ href, label, soon }) => ({ href, label, soon })),
];

/** Phone banner. Desktop uses the full sidebar list. */
export const BANNER_ITEMS: NavItem[] = [
  { href: "/", label: "Home" },
  ...FEATURES.filter((feature) => feature.banner).map(({ href, label, soon }) => ({
    href,
    label,
    soon,
  })),
];

export const HUB_CARDS: HubCard[] = FEATURES.map((feature) => ({
  ...feature,
  title: feature.label,
}));

export function isActivePath(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
