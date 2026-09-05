import Link from "next/link";
import { HUB_CARDS } from "@/lib/nav";
import { getReport } from "@/lib/data";
import { formatUpdated } from "@/lib/format";

export const revalidate = 3600;

export default async function Home() {
  const [median, players, trades] = await Promise.all([
    getReport("median-monday"),
    getReport("player-records"),
    getReport("trade-o-gami"),
  ]);
  const updated: Record<string, string | null> = {
    "/median-monday": formatUpdated(median?.last_updated),
    "/player-records": formatUpdated(players?.last_updated),
    "/trade-o-gami": formatUpdated(trades?.last_updated),
  };

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold">
        Commissioner&apos;s Report
      </h1>
      <p className="mt-2 max-w-xl text-sm md:text-base text-white/65">
        One place for the league&apos;s tables and projects. Click a section to
        open the report.
      </p>

      <ul className="mt-8 grid gap-3 sm:grid-cols-2">
        {HUB_CARDS.map((card) => {
          const last = updated[card.href];
          const inner = (
            <>
              <div className="flex items-baseline justify-between gap-2">
                <h2 className="text-lg font-semibold">{card.title}</h2>
                {card.soon ? (
                  <span className="text-[0.65rem] uppercase tracking-wide text-white/40">
                    Soon
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-white/65">{card.blurb}</p>
              {last ? (
                <p className="mt-3 text-xs text-white/45">Last updated {last}</p>
              ) : null}
            </>
          );

          if (card.soon) {
            return (
              <li
                key={card.title}
                className="rounded-lg border border-white/15 bg-white/5 px-4 py-4 text-white/50"
              >
                {inner}
              </li>
            );
          }

          return (
            <li key={card.title}>
              <Link
                href={card.href}
                className="block rounded-lg border border-white/20 bg-white/5 px-4 py-4 transition-colors hover:bg-white/10 hover:border-white/40"
              >
                {inner}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
