import { gridErrorResponse, gridJson, loadBoard } from "@/lib/grid-server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const board = await loadBoard(url.searchParams.get("date"), url.searchParams.get("anonId"));
    return gridJson(board);
  } catch (error) {
    return gridErrorResponse(error);
  }
}
