/**
 * Next.js → FastAPI SSE proxy.
 * Browser → /api/chat (same origin) → localhost:8000/api/v1/chat
 */
import { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      // Node.js fetch — SSE akışını bekletme
      // @ts-expect-error — Next.js node fetch extension
      duplex: "half",
    });
  } catch {
    return new Response("Backend bağlantısı kurulamadı", { status: 502 });
  }

  if (!backendRes.ok || !backendRes.body) {
    return new Response("Backend hatası", { status: backendRes.status });
  }

  // Doğrudan akışı geçir
  return new Response(backendRes.body, {
    headers: {
      "Content-Type":    "text/event-stream",
      "Cache-Control":   "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
