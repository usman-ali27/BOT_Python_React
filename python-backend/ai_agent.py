import os
import yfinance as yf
import pandas as pd
import numpy as np
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

class AIAgent:
    def __init__(self):
        # Local API-Free Lightweight NLP Model for Financial Sentiment
        self.sentiment_analyzer = None

    def _load_model(self):
        if self.sentiment_analyzer is None:
            print("Loading local NLP AI model (VADER)... (This runs entirely for free!)")
            try:
                nltk.data.find('sentiment/vader_lexicon.zip')
            except LookupError:
                nltk.download('vader_lexicon', quiet=True)
            self.sentiment_analyzer = SentimentIntensityAnalyzer()

    def analyze_news_sentiment(self, ticker="GC=F"):
        try:
            self._load_model()
            gold = yf.Ticker(ticker)
            news = gold.news
            
            if not news:
                 return {"sentiment": 0.0, "impact": "LOW", "market_condition": "SIDEWAYS", "reasoning": "No news data."}
            
            headlines = [n.get('title', '') for n in news[:5]]
            
            # Run Local NLP AI
            score_sum = 0
            for hl in headlines:
                scores = self.sentiment_analyzer.polarity_scores(hl)
                score_sum += scores['compound']
                
            avg_sentiment = score_sum / len(headlines) if headlines else 0
            
            # Data-driven market regime detection
            hist = gold.history(period="1mo")
            condition = "SIDEWAYS"
            impact = "LOW"
            if len(hist) > 10:
                recent_close = hist['Close'].iloc[-1]
                sma_10 = hist['Close'].rolling(window=10).mean().iloc[-1]
                
                # Volatility threshold (ATR proxy)
                hist['Range'] = hist['High'] - hist['Low']
                avg_range = hist['Range'].mean()
                recent_range = hist['Range'].iloc[-1]
                
                if recent_range > avg_range * 1.5:
                    condition = "VOLATILE"
                    impact = "HIGH"
                elif abs(recent_close - sma_10) > avg_range:
                    condition = "TRENDING"
                    impact = "MEDIUM"
                    
            if avg_sentiment > 0.2:
                reasoning = "Local NLP detected positive institutional sentiment. "
            elif avg_sentiment < -0.2:
                reasoning = "Local NLP detected bearish economic fears."
            else:
                reasoning = "Local NLP evaluated headlines as largely neutral."
                
            return {
                "sentiment": float(avg_sentiment),
                "impact": impact,
                "market_condition": condition,
                "reasoning": reasoning
            }
        except Exception as e:
            print(f"Local AI Pipeline Error: {e}")
            return {"sentiment": 0.0, "impact": "LOW", "market_condition": "SIDEWAYS", "reasoning": "Fallback due to AI error."}

ai_engine = AIAgent()
