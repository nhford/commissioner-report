import type { Metadata } from "next";
import { Suspense } from "react";
import ImmaculateGrid from "@/components/ImmaculateGrid";

export const metadata: Metadata = {
  title: "Immaculate Grid · Commissioner's Report",
  description:
    "A daily 3×3 of NFL franchises and fantasy achievements. Name a player who fits both headers.",
};

export default function ImmaculateGridPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold md:text-3xl">Immaculate Grid</h1>
      <p className="mt-2 max-w-xl text-sm text-white/70">
        A daily 3×3 for the fantasy season. The format comes from Sports Reference&apos;s
        Immaculate Grid.
      </p>
      <Suspense fallback={<p className="mt-8 text-sm text-white/60">Loading today’s grid…</p>}>
        <ImmaculateGrid />
      </Suspense>
    </div>
  );
}
