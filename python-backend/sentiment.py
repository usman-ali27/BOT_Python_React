from __future__ import annotations

import os

import requests

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except ImportError:  # pragma: no cover - fallback depends on local environment
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer

    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)


NEWS_API_KEY = os.getenv("NEWS_API_KEY", "08415fcb952145208b8fceee38232dbe")
NEWS_ENDPOINT = "https://newsapi.org/v2/everything"

analyzer = SentimentIntensityAnalyzer()


def fetch_gold_news():
    params = {
        "q": "gold OR XAUUSD",
        "language": "en",
        "sortBy": "publishedAt",
        "apiKey": NEWS_API_KEY,
        "pageSize": 10,
    }
    response = requests.get(NEWS_ENDPOINT, params=params, timeout=15)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        return [a["title"] + ". " + (a["description"] or "") for a in articles]
    return []


def get_sentiment_score(texts):
    if not texts:
        return 0.0
    scores = [analyzer.polarity_scores(text)["compound"] for text in texts]
    return sum(scores) / len(scores)


def gold_sentiment():
    news = fetch_gold_news()
    return get_sentiment_score(news)
