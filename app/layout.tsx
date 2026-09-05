import type { Metadata } from "next";
import { Geist } from "next/font/google";
import SiteChrome from "@/components/SiteChrome";
import { getReport } from "@/lib/data";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Commissioner's Report",
  description:
    "League reports for median standings, player win-loss records, and more.",
};

export const viewport = {
  themeColor: "#262626",
};

export const revalidate = 3600;

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const median = await getReport("median-monday");

  return (
    <html
      lang="en"
      className={`${geistSans.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-neutral-800 text-white">
        <SiteChrome
          week={median?.current_week ?? undefined}
          season={median?.season ?? undefined}
        >
          {children}
        </SiteChrome>
      </body>
    </html>
  );
}
