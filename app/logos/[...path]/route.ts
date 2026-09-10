import { logoStorageUrl } from "@/lib/logos";

const REVALIDATE = 60 * 60 * 24 * 30;
const CACHE_CONTROL =
  "public, max-age=2592000, stale-while-revalidate=31536000";

function safePath(parts: string[]): string | null {
  if (!parts.length) return null;
  for (const part of parts) {
    if (!part || part === "." || part === ".." || part.includes("\\")) {
      return null;
    }
  }
  return parts.join("/");
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const url = logoStorageUrl(safePath(path));
  if (!url) return new Response("Not found", { status: 404 });

  const upstream = await fetch(url, {
    next: { revalidate: REVALIDATE, tags: ["logos"] },
  });
  if (!upstream.ok) {
    return new Response("Not found", { status: upstream.status });
  }

  const headers = new Headers();
  headers.set(
    "Content-Type",
    upstream.headers.get("Content-Type") ?? "application/octet-stream",
  );
  headers.set("Cache-Control", CACHE_CONTROL);
  const etag = upstream.headers.get("ETag");
  if (etag) headers.set("ETag", etag);

  return new Response(upstream.body, { status: 200, headers });
}
