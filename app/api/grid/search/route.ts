import { gridErrorResponse, gridJson, searchPlayers } from "@/lib/grid-server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const players = await searchPlayers(url.searchParams.get("q"));
    return gridJson({ players });
  } catch (error) {
    return gridErrorResponse(error);
  }
}
