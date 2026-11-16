import type { Metadata } from "next";
import SamsStuff, { SAM_HOW } from "@/components/SamsStuff";
import { getSamSource } from "@/lib/data";
import { samViews } from "@/lib/sam";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Sam's Stuff · Commissioner's Report",
  description:
    "Start/sit accuracy and all-play expected record for each regular season.",
};

export default async function SamsStuffPage() {
  const { players, teams } = await getSamSource();
  const seasons = samViews(players, teams);

  return (
    <div>
      <h1 className="text-2xl font-bold md:text-3xl">Sam&apos;s Stuff</h1>
      <details className="mt-3 max-w-2xl md:hidden">
        <summary className="min-h-11 cursor-pointer text-sm text-white/70 underline decoration-white/40 underline-offset-2">
          How Sam&apos;s Stuff works
        </summary>
        <p className="mt-2 text-sm text-white/70">{SAM_HOW}</p>
      </details>
      <p className="mt-3 hidden max-w-2xl text-sm text-white/70 md:block">
        {SAM_HOW}
      </p>
      <div className="mt-6">
        <SamsStuff seasons={seasons} />
      </div>
    </div>
  );
}
