// Utility to fetch gold sentiment from backend
export async function fetchGoldSentiment(): Promise<number> {
  try {
    const res = await fetch("/api/sentiment/gold");
    if (!res.ok) return 0;
    const data = await res.json();
    return data.sentiment ?? 0;
  } catch {
    return 0;
  }
}
