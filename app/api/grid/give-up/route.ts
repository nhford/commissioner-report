import { giveUp, gridErrorResponse, gridJson } from "@/lib/grid-server";

export const dynamic = "force-dynamic";

type Body = {
  date?: string;
  anonId?: string;
};

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Body;
    const result = await giveUp(body.date ?? null, body.anonId ?? null);
    return gridJson(result);
  } catch (error) {
    if (error instanceof SyntaxError) return gridJson({ error: "Invalid request." }, 400);
    return gridErrorResponse(error);
  }
}
