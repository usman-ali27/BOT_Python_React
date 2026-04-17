// Google GenAI sdk is currently unused here as we use the local Python NLP model backend.

export async function analyzeNewsSentiment(newsHeadline: string) {
  try {
    const response = await fetch('/api/ai/insight');
    if (!response.ok) throw new Error("Backend connection failed.");
    return await response.json();
  } catch (error) {
    console.error("AI Analysis failed:", error);
    return { sentiment: 0, impact: 'LOW', market_condition: 'SIDEWAYS', reasoning: "AI unavailable" };
  }
}

export async function getMarketInsight(marketData: any) {
  try {
    const res = await analyzeNewsSentiment("GC=F");
    const advice = `Market is ${res.market_condition}. ${res.reasoning} Impact: ${res.impact}`;
    return advice;
  } catch (error) {
    return "Consolidating near pivot. Maintain defensive stance.";
  }
}
