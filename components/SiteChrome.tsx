"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Footer from "./Footer";
import { BANNER_ITEMS, isActivePath, NAV_ITEMS } from "@/lib/nav";

type Props = {
  week?: number;
  season?: number;
  children: React.ReactNode;
};

function NavLink({
  href,
  label,
  soon,
  pathname,
  variant,
}: {
  href: string;
  label: string;
  soon?: boolean;
  pathname: string;
  variant: "side" | "top";
}) {
  const active = !soon && isActivePath(pathname, href);

  if (soon) {
    return (
      <span
        className={
          variant === "side"
            ? "block px-3 py-1.5 text-sm text-white/35 cursor-default"
            : "shrink-0 px-2 py-1 text-sm text-white/35"
        }
      >
        {label}
        <span className="ml-1 text-[0.65rem] uppercase tracking-wide">
          soon
        </span>
      </span>
    );
  }

  if (variant === "side") {
    return (
      <Link
        href={href}
        className={`block px-3 py-1.5 text-sm transition-colors ${
          active
            ? "bg-white/10 font-semibold text-white"
            : "text-white/70 hover:bg-white/5 hover:text-white hover:underline hover:underline-offset-2 hover:decoration-emerald-400"
        }`}
      >
        {label}
      </Link>
    );
  }

  return (
    <Link
      href={href}
      className={`shrink-0 px-1.5 py-1 text-sm whitespace-nowrap ${
        active
          ? "font-semibold text-white underline underline-offset-4 decoration-emerald-400"
          : "text-white/70 hover:text-white hover:underline hover:underline-offset-2 hover:decoration-emerald-400"
      }`}
    >
      {label}
    </Link>
  );
}

export default function SiteChrome({ week, season, children }: Props) {
  const pathname = usePathname();
  const issue =
    week && season
      ? `Week ${week} · ${season}`
      : week
        ? `Week ${week}`
        : "League reports";

  return (
    <div className="min-h-full">
      <aside className="hidden md:flex fixed inset-y-0 left-0 w-56 flex-col border-r border-white/15 px-4 py-6">
        <Link href="/" className="block px-3">
          <p className="text-lg font-bold leading-tight tracking-tight">
            Commissioner&apos;s Report
          </p>
          <p className="mt-1 text-xs text-white/50">{issue}</p>
        </Link>
        <nav className="mt-8 flex flex-col gap-0.5" aria-label="Sections">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.label}
              {...item}
              pathname={pathname}
              variant="side"
            />
          ))}
        </nav>
        <p className="mt-auto px-3 text-xs text-white/40">
          powered by ESPN
        </p>
      </aside>

      <header className="md:hidden sticky top-0 z-20 border-b border-white/15 bg-neutral-800">
        <div className="flex items-center gap-3 px-3 pb-5 pt-3">
          <Link href="/" className="relative shrink-0 self-start">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/favicon-dark.png"
              alt="Commissioner's Report"
              className="h-9 w-9 object-contain"
            />
            <p className="absolute left-0 top-9 mt-0.5 whitespace-nowrap text-[0.65rem] leading-none text-white/50">
              {issue}
            </p>
          </Link>
          <nav
            className="min-w-0 flex-1 overflow-x-auto"
            aria-label="Sections"
          >
            <div className="flex items-center gap-1">
              {BANNER_ITEMS.map((item) => (
                <NavLink
                  key={item.label}
                  {...item}
                  pathname={pathname}
                  variant="top"
                />
              ))}
            </div>
          </nav>
        </div>
      </header>

      <div className="md:ml-56 min-h-screen flex flex-col px-4 py-6 sm:px-8">
        <main className="w-full max-w-6xl flex-1">{children}</main>
        <Footer />
      </div>
    </div>
  );
}
