import { revalidatePath } from "next/cache";
import { NextResponse } from "next/server";

const PATHS = ["/", "/median-monday", "/player-records", "/trade-o-gami"];

export async function POST(request: Request) {
  const secret = request.headers.get("x-revalidate-secret");
  if (!process.env.REVALIDATE_SECRET || secret !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  for (const path of PATHS) {
    revalidatePath(path);
  }

  return NextResponse.json({ ok: true, paths: PATHS });
}
