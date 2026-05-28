import type { ApiResponse } from "./types";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function fetchRegimeReport(includeNews = true): Promise<ApiResponse> {
  const url = `${BACKEND}/api/v1/regime-report/current?include_news=${includeNews}`;
  const res = await fetch(url, { next: { revalidate: 60 } }); // 60s cache
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return res.json();
}
