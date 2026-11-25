import type { Metadata } from "next";
import ReportPage from "@/components/ReportPage";
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
    <ReportPage title="Sam's Stuff" how={SAM_HOW}>
      <SamsStuff seasons={seasons} />
    </ReportPage>
  );
}
