import { gridErrorResponse, gridJson, submitGuess } from "@/lib/grid-server";

export const dynamic = "force-dynamic";

type Body = {
  date?: string;
  anonId?: string;
  cell?: number;
  playerId?: string;
};

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Body;
    const result = await submitGuess({
      date: body.date ?? null,
      anonId: body.anonId ?? null,
      cell: Number(body.cell),
      playerId: body.playerId ?? "",
    });
    return gridJson(result);
  } catch (error) {
    if (error instanceof SyntaxError) return gridJson({ error: "Invalid request." }, 400);
    return gridErrorResponse(error);
  }
}
