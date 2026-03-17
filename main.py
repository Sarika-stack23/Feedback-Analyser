# ============================================================
# FEEDBACK ANALYSER — main.py
# Complete Production App
# ============================================================


# ── SECTION 1: IMPORTS ──────────────────────────────────────
import os
import re
import io
import time
import uuid
import json
import random
import warnings
import datetime
import traceback
from io import BytesIO
from collections import Counter

from dotenv import load_dotenv
load_dotenv()  # ← loads .env file at startup

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import requests
import matplotlib
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

matplotlib.use("Agg")
warnings.filterwarnings("ignore")

from transformers import pipeline
from fpdf import FPDF
from wordcloud import WordCloud

try:
    from google_play_scraper import reviews as gp_reviews, Sort
    GOOGLE_PLAY_AVAILABLE = True
except ImportError:
    GOOGLE_PLAY_AVAILABLE = False

try:
    import yake
    YAKE_AVAILABLE = True
except ImportError:
    YAKE_AVAILABLE = False


# ── SECTION 2: CONFIG & CONSTANTS ───────────────────────────
APP_TITLE = "Feedback Analyser"
PAGE_ICON = "📊"
LAYOUT = "wide"

DEFAULT_PLAY_APP_ID = "com.spotify.music"
DEFAULT_APP_STORE_ID = "324684580"   # Spotify
DEFAULT_COUNTRY = "us"
DEFAULT_LANG = "en"

DATE_FORMAT = "%Y-%m-%d"

SENTIMENT_COLORS = {
    "positive": "#2ecc71",
    "neutral":  "#f39c12",
    "negative": "#e74c3c",
}

PRIORITY_COLORS = {
    "Critical": "#e74c3c",
    "Moderate": "#f39c12",
    "Low":      "#2ecc71",
}

CHART_TEMPLATE = "plotly_dark"


# ── SECTION 3: DATA FETCHERS ────────────────────────────────

def fetch_google_play_reviews(
    app_id: str,
    country: str = "us",
    lang: str = "en",
    count: int = 200,
) -> pd.DataFrame:
    """Fetch reviews from Google Play Store."""
    if not GOOGLE_PLAY_AVAILABLE:
        st.warning("google-play-scraper not installed. Run: pip install google-play-scraper")
        return pd.DataFrame()

    try:
        result, _ = gp_reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=count,
        )

        rows = []
        for r in result:
            at = r.get("at", datetime.datetime.now())
            date_obj = at.date() if hasattr(at, "date") else datetime.date.today()
            rows.append(
                {
                    "review_id": str(r.get("reviewId", uuid.uuid4())),
                    "source":    "Google Play",
                    "date":      date_obj,
                    "rating":    int(r.get("score", 3)),
                    "text":      r.get("content", ""),
                    "thumbs_up": r.get("thumbsUpCount", 0),
                }
            )
        return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"Google Play fetch error: {e}")
        return pd.DataFrame()


def fetch_app_store_reviews(
    app_id: str,
    country: str = "us",
    pages: int = 5,
) -> pd.DataFrame:
    """Fetch reviews from Apple App Store via RSS JSON feed."""
    rows = []

    for page in range(1, pages + 1):
        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"page={page}/id={app_id}/sortby=mostrecent/json"
        )

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            entries = data.get("feed", {}).get("entry", [])
            if not entries:
                break

            start_idx = 1 if isinstance(entries, list) and "im:name" in entries[0] else 0

            for entry in entries[start_idx:]:
                try:
                    rating_val = entry.get("im:rating", {}).get("label", "3")
                    date_str   = entry.get("updated", {}).get("label", "")

                    try:
                        date_obj = datetime.datetime.fromisoformat(date_str[:10]).date()
                    except Exception:
                        date_obj = datetime.date.today()

                    text = entry.get("content", {}).get("label", "")
                    rows.append(
                        {
                            "review_id": str(uuid.uuid4()),
                            "source":    "App Store",
                            "date":      date_obj,
                            "rating":    int(rating_val),
                            "text":      text,
                            "thumbs_up": 0,
                        }
                    )
                except Exception:
                    continue

            time.sleep(0.5)

        except requests.exceptions.Timeout:
            st.warning(f"App Store timeout on page {page}. Continuing with fetched data.")
            break
        except requests.exceptions.RequestException as e:
            st.warning(f"App Store network error: {e}")
            break
        except Exception as e:
            st.warning(f"App Store parse error on page {page}: {e}")
            break

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def load_csv_reviews(uploaded_file) -> pd.DataFrame:
    """Load reviews from an uploaded CSV file with auto column detection."""
    try:
        df = pd.read_csv(uploaded_file)
        col_map = {}

        for col in df.columns:
            cl = col.lower().strip()
            if any(k in cl for k in ["review", "text", "comment", "feedback", "body", "content"]):
                col_map["text"] = col
            elif any(k in cl for k in ["date", "time", "created", "submitted", "at"]):
                col_map["date"] = col
            elif any(k in cl for k in ["rating", "score", "star", "grade"]):
                col_map["rating"] = col

        if "text" not in col_map:
            for col in df.columns:
                if df[col].dtype == object:
                    col_map["text"] = col
                    break

        if "text" not in col_map:
            st.error(
                "Could not find a text/review column in CSV. "
                "Please ensure your CSV has a column with review text."
            )
            return pd.DataFrame()

        rows = []
        for _, row in df.iterrows():
            text = str(row.get(col_map["text"], ""))

            date_obj = datetime.date.today()
            if "date" in col_map:
                try:
                    date_obj = pd.to_datetime(row[col_map["date"]]).date()
                except Exception:
                    pass

            rating = 3
            if "rating" in col_map:
                try:
                    rating = max(1, min(5, int(float(row[col_map["rating"]]))))
                except Exception:
                    pass

            if text.strip() and text.lower() != "nan":
                rows.append(
                    {
                        "review_id": str(uuid.uuid4()),
                        "source":    "CSV",
                        "date":      date_obj,
                        "rating":    rating,
                        "text":      text,
                        "thumbs_up": 0,
                    }
                )

        return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"CSV loading error: {e}")
        return pd.DataFrame()


# ── SECTION 4: DATA PREPROCESSING ───────────────────────────

def clean_text(text: str) -> str:
    """Remove HTML, URLs, and normalise whitespace."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"[^\w\s.,!?'-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def standardize_reviews(dfs: list) -> pd.DataFrame:
    """Merge all source dataframes into one unified schema."""
    valid = [d for d in dfs if d is not None and not d.empty]
    if not valid:
        return pd.DataFrame()

    combined = pd.concat(valid, ignore_index=True)

    for col in ["review_id", "source", "date", "rating", "text", "thumbs_up"]:
        if col not in combined.columns:
            combined[col] = None

    combined["text"]   = combined["text"].apply(clean_text)
    combined           = combined[combined["text"].str.len() > 10].copy()
    combined           = combined.drop_duplicates(subset=["text"]).reset_index(drop=True)
    combined["date"]   = pd.to_datetime(combined["date"], errors="coerce").dt.date
    combined           = combined.dropna(subset=["date"])
    combined["rating"] = (
        pd.to_numeric(combined["rating"], errors="coerce")
        .fillna(3)
        .astype(int)
        .clip(1, 5)
    )
    combined["week"]   = pd.to_datetime(combined["date"]).dt.to_period("W").astype(str)

    return combined.reset_index(drop=True)


# ── SECTION 5: SENTIMENT ANALYSIS ───────────────────────────

@st.cache_resource(show_spinner="Loading sentiment model…")
def load_sentiment_model():
    """Load a HuggingFace sentiment pipeline (cached across reruns)."""
    for model_name in [
        "cardiffnlp/twitter-roberta-base-sentiment-latest",
        "distilbert-base-uncased-finetuned-sst-2-english",
    ]:
        try:
            return pipeline(
                "sentiment-analysis",
                model=model_name,
                max_length=512,
                truncation=True,
            )
        except Exception:
            continue
    st.warning("ML model unavailable — using rating-based sentiment fallback.")
    return None


def rating_to_sentiment(rating: int) -> tuple:
    """Map star rating → (label, confidence) for fallback use."""
    if rating >= 4:
        return "positive", 0.85
    if rating == 3:
        return "neutral", 0.70
    return "negative", 0.85


_LABEL_MAP = {
    "POSITIVE": "positive", "LABEL_2": "positive", "positive": "positive",
    "NEGATIVE": "negative", "LABEL_0": "negative", "negative": "negative",
    "NEUTRAL":  "neutral",  "LABEL_1": "neutral",  "neutral":  "neutral",
}


def run_sentiment_analysis(df: pd.DataFrame, model=None) -> pd.DataFrame:
    """Append sentiment_label and sentiment_score columns to df."""
    df = df.copy()
    labels, scores = [], []

    if model is None:
        for _, row in df.iterrows():
            lbl, sc = rating_to_sentiment(row.get("rating", 3))
            labels.append(lbl)
            scores.append(sc)
    else:
        texts      = df["text"].tolist()
        batch_size = 16
        progress   = st.progress(0, text="Analysing sentiment…")

        for i in range(0, len(texts), batch_size):
            batch = [t[:512] for t in texts[i : i + batch_size]]
            try:
                results = model(batch)
                for r in results:
                    raw = r["label"].upper()
                    labels.append(_LABEL_MAP.get(raw, _LABEL_MAP.get(r["label"], "neutral")))
                    scores.append(round(r["score"], 3))
            except Exception:
                labels.extend(["neutral"] * len(batch))
                scores.extend([0.5] * len(batch))

            progress.progress(
                min((i + batch_size) / len(texts), 1.0),
                text=f"Analysing sentiment… {min(i + batch_size, len(texts))}/{len(texts)}",
            )

        progress.empty()

    df["sentiment_label"] = labels
    df["sentiment_score"] = scores
    return df


def extract_keywords(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'keywords' column with extracted key phrases per review."""
    df = df.copy()

    _stopwords = {
        "this", "that", "with", "have", "from", "they", "will", "been", "were",
        "when", "what", "your", "more", "some", "than", "just", "also", "very",
        "there", "their", "which", "about", "would", "could", "should", "after",
    }

    def get_kws(text: str) -> list:
        if not text:
            return []
        if YAKE_AVAILABLE:
            try:
                kw_extractor = yake.KeywordExtractor(n=2, top=5, dedupLim=0.7)
                return [kw for kw, _ in kw_extractor.extract_keywords(text)]
            except Exception:
                pass
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        return [w for w in words if w not in _stopwords][:5]

    df["keywords"] = df["text"].apply(get_kws)
    return df


# ── SECTION 6: TREND DETECTION ──────────────────────────────

def calculate_daily_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily aggregated sentiment metrics with 7-day rolling average."""
    if df.empty:
        return pd.DataFrame()

    tmp = df.copy()
    tmp["date"]          = pd.to_datetime(tmp["date"])
    tmp["sentiment_num"] = tmp["sentiment_label"].map({"positive": 1, "neutral": 0, "negative": -1}).fillna(0)

    daily = (
        tmp.groupby("date")
        .agg(
            avg_sentiment  = ("sentiment_num",   "mean"),
            avg_rating     = ("rating",          "mean"),
            review_count   = ("review_id",       "count"),
            positive_count = ("sentiment_label", lambda x: (x == "positive").sum()),
            negative_count = ("sentiment_label", lambda x: (x == "negative").sum()),
            neutral_count  = ("sentiment_label", lambda x: (x == "neutral").sum()),
        )
        .reset_index()
        .sort_values("date")
    )

    daily["rolling_sentiment"] = daily["avg_sentiment"].rolling(window=7, min_periods=1).mean()
    return daily


def calculate_week_over_week(daily_df: pd.DataFrame) -> dict:
    """Return week-over-week sentiment change stats."""
    if daily_df.empty:
        return {"change": 0, "direction": "stable", "message": "No data available"}

    daily_df = daily_df.sort_values("date")
    n        = len(daily_df)

    # Need at least 2 days to compare
    if n < 2:
        return {"change": 0, "direction": "stable", "message": "Need more data for trend comparison"}

    # Split available data in half for comparison
    half     = max(1, n // 2)
    last_half = daily_df.tail(half)["avg_sentiment"].mean()
    prev_half = daily_df.iloc[:half]["avg_sentiment"].mean()
    change    = ((last_half - prev_half) / max(abs(prev_half), 1e-9)) * 100

    period = "week" if n >= 14 else f"{half}-day period"

    if change > 10:
        direction = "improving"
        message   = f"Sentiment improving by {change:.1f}% vs previous {period}"
    elif change < -10:
        direction = "declining"
        message   = f"Sentiment declining by {abs(change):.1f}% vs previous {period}"
    else:
        direction = "stable"
        message   = f"Sentiment stable (+-{abs(change):.1f}% vs previous {period})"

    return {"change": round(change, 2), "direction": direction, "message": message}


def detect_spikes(daily_df: pd.DataFrame, threshold: float = 2.0) -> list:
    """Flag dates where negative review count is >threshold std-devs above mean."""
    if daily_df.empty or len(daily_df) < 7:
        return []

    daily_df  = daily_df.sort_values("date")
    mean_neg  = daily_df["negative_count"].mean()
    std_neg   = daily_df["negative_count"].std()

    spikes = []
    for _, row in daily_df.iterrows():
        if std_neg > 0 and row["negative_count"] > mean_neg + threshold * std_neg:
            spikes.append(
                {
                    "date":           str(row["date"])[:10],
                    "negative_count": int(row["negative_count"]),
                    "z_score":        round((row["negative_count"] - mean_neg) / std_neg, 2),
                }
            )
    return spikes


# ── SECTION 7: ISSUE PRIORITIZATION ─────────────────────────

def score_issues(df: pd.DataFrame) -> pd.DataFrame:
    """Build a scored issue table from negative review keywords."""
    if df.empty or "keywords" not in df.columns:
        return pd.DataFrame()

    neg_df = df[df["sentiment_label"] == "negative"].copy()
    if neg_df.empty:
        return pd.DataFrame()

    all_kws = []
    for _, row in neg_df.iterrows():
        kws = row.get("keywords", [])
        if isinstance(kws, list):
            all_kws.extend(kws)

    if not all_kws:
        for _, row in neg_df.iterrows():
            words = re.findall(r"\b[a-z]{4,}\b", str(row["text"]).lower())
            all_kws.extend(words[:3])

    cutoff = datetime.date.today() - datetime.timedelta(days=7)
    rows   = []

    for keyword, freq in Counter(all_kws).most_common(20):
        match = neg_df[neg_df["text"].str.lower().str.contains(keyword, na=False)]
        if match.empty:
            continue

        sample = match.iloc[0]["text"]
        sample = sample[:150] + "…" if len(sample) > 150 else sample

        rows.append(
            {
                "issue":               keyword,
                "frequency":           freq,
                "avg_sentiment_score": round(match["sentiment_score"].mean(), 3),
                "recent_count":        int(match[match["date"] >= cutoff].shape[0]),
                "total_reviews":       len(match),
                "sample_quote":        sample,
            }
        )

    return pd.DataFrame(rows)


def assign_priority(issues_df: pd.DataFrame) -> pd.DataFrame:
    """Score and bucket issues into Critical / Moderate / Low tiers."""
    if issues_df.empty:
        return issues_df

    df = issues_df.copy()
    max_freq   = df["frequency"].max()   or 1
    max_recent = df["recent_count"].max() or 1

    df["priority_score"] = (
        (df["frequency"]           / max_freq)   * 0.4
        + df["avg_sentiment_score"]              * 0.4
        + (df["recent_count"]      / max_recent) * 0.2
    )

    def tier(score):
        return "Critical" if score >= 0.65 else ("Moderate" if score >= 0.35 else "Low")

    df["priority"] = df["priority_score"].apply(tier)
    return df.sort_values("priority_score", ascending=False).reset_index(drop=True)


def get_sample_quotes(df: pd.DataFrame, keyword: str, n: int = 3) -> list:
    """Return n sample negative reviews that mention keyword."""
    match = df[
        df["text"].str.lower().str.contains(keyword, na=False)
        & (df["sentiment_label"] == "negative")
    ]
    return [
        {
            "text":   row["text"][:200],
            "date":   str(row["date"]),
            "source": row["source"],
            "rating": row["rating"],
        }
        for _, row in match.head(n).iterrows()
    ]


# ── SECTION 8: BONUS FEATURES ───────────────────────────────

def generate_demo_data() -> pd.DataFrame:
    """Generate realistic sample reviews for demo mode (no API needed)."""
    random.seed(42)
    today = datetime.date.today()

    positive_reviews = [
        "Amazing app, love all the features! Works perfectly every time.",
        "Best music streaming service I have used. Highly recommend.",
        "Great sound quality and huge library. Worth every penny.",
        "The new update is fantastic. So smooth and easy to use.",
        "Love the personalized playlists. Always finds exactly what I want.",
        "Excellent app. Customer support resolved my issue very quickly.",
        "Perfect for working out. The beats per minute filter is brilliant.",
        "Discover Weekly is always spot on. Best algorithm out there.",
        "Seamless sync across all devices. Works great on everything.",
        "Sleep timer feature is amazing. Fall asleep to music every night.",
    ]
    negative_reviews = [
        "App keeps crashing every time I try to open it. Very frustrating.",
        "Too many ads in free version. Impossible to enjoy music.",
        "Premium subscription is too expensive for what you get.",
        "Cannot listen without shuffle on free account. Terrible restriction.",
        "Battery drain is terrible. Heats up my phone within minutes.",
        "Constant buffering even on fast wifi. Streaming quality is bad.",
        "Login broken after update. Lost all my saved playlists and songs.",
        "Downloaded songs disappeared after latest update. Months of downloads gone.",
        "Search function is broken. Cannot find songs by lyrics anymore.",
        "Charged twice for premium subscription. Billing error unresolved.",
    ]
    neutral_reviews = [
        "Average app. Gets the job done but nothing special.",
        "Decent features but competitors offer more for less money.",
        "Mixed feelings. Some features are great but too many bugs.",
        "Okay for basic music streaming. Not worth premium price.",
        "Works most of the time. Occasional bugs here and there.",
    ]

    rows = []
    for i in range(150):
        days_ago = random.randint(0, 60)
        date     = today - datetime.timedelta(days=days_ago)
        r        = random.random()

        if r < 0.45:
            text    = random.choice(positive_reviews)
            rating  = random.choice([4, 5])
            sentiment = "positive"
            score   = round(random.uniform(0.80, 0.98), 3)
        elif r < 0.75:
            text    = random.choice(negative_reviews)
            rating  = random.choice([1, 2])
            sentiment = "negative"
            score   = round(random.uniform(0.80, 0.95), 3)
        else:
            text    = random.choice(neutral_reviews)
            rating  = 3
            sentiment = "neutral"
            score   = round(random.uniform(0.60, 0.80), 3)

        rows.append({
            "review_id":       str(uuid.uuid4()),
            "source":          random.choice(["Google Play", "App Store", "CSV"]),
            "date":            date,
            "rating":          rating,
            "text":            text,
            "thumbs_up":       random.randint(0, 50),
            "sentiment_label": sentiment,
            "sentiment_score": score,
            "keywords":        text.lower().split()[:4],
            "week":            pd.Period(date, "W").strftime("%Y-W%V"),
        })

    return pd.DataFrame(rows)


def predict_sentiment_trend(daily_df: pd.DataFrame, days_ahead: int = 14) -> pd.DataFrame:
    """Use linear regression to forecast sentiment for next N days."""
    if daily_df.empty or len(daily_df) < 7:
        return pd.DataFrame()

    daily_df = daily_df.sort_values("date").copy()
    daily_df["day_num"] = range(len(daily_df))

    X = daily_df[["day_num"]].values
    y = daily_df["rolling_sentiment"].values

    model = LinearRegression()
    model.fit(X, y)

    last_day   = daily_df["day_num"].max()
    last_date  = pd.to_datetime(daily_df["date"].max())
    future_days = np.array([[last_day + i] for i in range(1, days_ahead + 1)])
    predictions = model.predict(future_days).clip(-1, 1)

    future_dates = [last_date + datetime.timedelta(days=i) for i in range(1, days_ahead + 1)]
    return pd.DataFrame({
        "date":            future_dates,
        "predicted_sentiment": predictions,
    })


def chart_prediction(daily_df: pd.DataFrame, pred_df: pd.DataFrame) -> go.Figure:
    """Chart historical sentiment + forecast."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=daily_df["date"], y=daily_df["rolling_sentiment"],
        mode="lines", name="Historical (7-day avg)",
        line=dict(color="#3498db", width=2),
    ))

    if not pred_df.empty:
        fig.add_trace(go.Scatter(
            x=pred_df["date"], y=pred_df["predicted_sentiment"],
            mode="lines", name="Forecast (14 days)",
            line=dict(color="#e67e22", width=2, dash="dash"),
        ))

        upper = (pred_df["predicted_sentiment"] + 0.1).clip(-1, 1)
        lower = (pred_df["predicted_sentiment"] - 0.1).clip(-1, 1)
        fig.add_trace(go.Scatter(
            x=pd.concat([pred_df["date"], pred_df["date"][::-1]]),
            y=pd.concat([upper, lower[::-1]]),
            fill="toself", fillcolor="rgba(230,126,34,0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="Confidence Band", showlegend=True,
        ))

    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.4)
    fig.update_layout(
        title="Sentiment Forecast — Next 14 Days",
        xaxis_title="Date", yaxis_title="Sentiment Score (-1 to 1)",
        template=CHART_TEMPLATE, height=380,
    )
    return fig


LANGUAGE_LABELS = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "ru": "Russian",
    "it": "Italian",
}


def detect_language_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Heuristic language detection based on common word patterns."""
    lang_patterns = {
        "Spanish": r"\b(que|el|la|de|en|es|por|con|no|se)\b",
        "French":  r"\b(le|la|les|de|et|en|que|pour|dans|est)\b",
        "German":  r"\b(die|der|das|und|ist|ich|nicht|ein|mit|von)\b",
        "Hindi":   r"[\u0900-\u097F]",
        "Japanese":r"[\u3040-\u309F\u30A0-\u30FF]",
        "Korean":  r"[\uAC00-\uD7AF]",
        "Chinese": r"[\u4E00-\u9FFF]",
        "Arabic":  r"[\u0600-\u06FF]",
        "Russian": r"[\u0400-\u04FF]",
    }

    counts = Counter({"English": 0})
    for text in df["text"].fillna(""):
        detected = "English"
        for lang, pattern in lang_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                detected = lang
                break
        counts[detected] += 1

    return pd.DataFrame(
        [{"language": lang, "count": cnt} for lang, cnt in counts.most_common()],
    )


def check_sentiment_alerts(daily_df: pd.DataFrame, threshold: float = -0.3) -> list:
    """Return alert messages if recent sentiment crosses threshold."""
    alerts = []
    if daily_df.empty:
        return alerts

    recent = daily_df.tail(3)
    avg    = recent["avg_sentiment"].mean()

    if avg < threshold:
        alerts.append({
            "level":   "CRITICAL",
            "message": f"Sentiment critically low ({avg:.2f}) over last 3 days. Immediate review needed.",
            "value":   round(avg, 3),
        })
    elif avg < 0:
        alerts.append({
            "level":   "WARNING",
            "message": f"Sentiment negative ({avg:.2f}) over last 3 days. Monitor closely.",
            "value":   round(avg, 3),
        })

    spike_days = daily_df[daily_df["negative_count"] > daily_df["negative_count"].mean() * 2]
    if not spike_days.empty:
        alerts.append({
            "level":   "WARNING",
            "message": f"Negative review spike detected on {len(spike_days)} day(s). Check Issues tab.",
            "value":   int(spike_days["negative_count"].max()),
        })

    return alerts


# ── SECTION 8b: AI PROMPTS (GROQ) ────────────────────────────

def groq_ai_insight(
    issues_df: pd.DataFrame,
    df: pd.DataFrame,
    wow: dict,
    groq_api_key: str,
) -> str:
    """
    Send top issues + sentiment summary to Groq (Llama3) and return
    an AI-generated insight paragraph for the dashboard.
    Get a free API key at https://console.groq.com
    """
    if not groq_api_key or groq_api_key.strip() == "":
        return ""

    try:
        total     = len(df)
        pos_pct   = round((df["sentiment_label"] == "positive").sum() / max(total, 1) * 100, 1)
        neg_pct   = round((df["sentiment_label"] == "negative").sum() / max(total, 1) * 100, 1)
        avg_rating = round(df["rating"].mean(), 2) if total else 0

        top_issues = ""
        if not issues_df.empty:
            critical = issues_df[issues_df["priority"] == "Critical"].head(5)
            for _, row in critical.iterrows():
                top_issues += f"- {row['issue'].title()}: mentioned {row['frequency']} times\n"

        prompt = f"""You are a product manager assistant analysing app store reviews.

Here is a summary of recent user feedback:
- Total reviews: {total}
- Positive sentiment: {pos_pct}%
- Negative sentiment: {neg_pct}%
- Average rating: {avg_rating}/5
- Trend: {wow.get('message', 'Not available')}

Top critical issues reported by users:
{top_issues if top_issues else 'No critical issues detected.'}

Please provide:
1. A 2-sentence executive summary of the current feedback situation
2. Top 3 specific, actionable recommendations for the product team
3. One positive highlight to share with the team

Keep your response concise and business-focused. Use plain text, no markdown."""

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.1-8b-instant",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  400,
                "temperature": 0.4,
            },
            timeout=15,
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"Groq API error {response.status_code}: {response.text[:100]}"

    except requests.exceptions.Timeout:
        return "Groq request timed out. Check your internet connection."
    except Exception as e:
        return f"AI insight unavailable: {str(e)[:80]}"


def groq_suggest_response(review_text: str, groq_api_key: str) -> str:
    """
    Given a single negative review, ask Groq to suggest a
    professional response that a support team could send.
    """
    if not groq_api_key or groq_api_key.strip() == "":
        return ""

    try:
        prompt = f"""You are a professional customer support agent for a mobile app company.

A user left this negative review:
\"{review_text}\"

Write a short, empathetic, professional response (2-3 sentences) that:
- Acknowledges their frustration
- Apologises sincerely
- Offers a concrete next step

Plain text only, no markdown, no emojis."""

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":       "llama-3.1-8b-instant",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  150,
                "temperature": 0.5,
            },
            timeout=10,
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        return ""

    except Exception:
        return ""


# ── SECTION 8c: EMAIL PARSER ──────────────────────────────────

def parse_email_text(raw_email: str) -> dict:
    """
    Parse a raw email string (plain text or .eml content) and extract
    the feedback body, sender, and date.
    Returns a dict with keys: text, date, subject, sender
    """
    result = {
        "text":    "",
        "date":    datetime.date.today(),
        "subject": "",
        "sender":  "",
    }

    lines = raw_email.strip().splitlines()
    body_lines  = []
    in_body     = False
    header_done = False

    for line in lines:
        stripped = line.strip()

        # Parse headers
        if not header_done:
            if stripped.lower().startswith("from:"):
                result["sender"] = stripped[5:].strip()
                continue
            if stripped.lower().startswith("subject:"):
                result["subject"] = stripped[8:].strip()
                continue
            if stripped.lower().startswith("date:"):
                date_str = stripped[5:].strip()
                try:
                    parsed = pd.to_datetime(date_str, errors="coerce")
                    if not pd.isnull(parsed):
                        result["date"] = parsed.date()
                except Exception:
                    pass
                continue
            if stripped == "":
                header_done = True
                in_body     = True
                continue

        # Collect body
        if in_body:
            # Skip quoted reply lines (lines starting with >)
            if not stripped.startswith(">"):
                body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Remove email signatures (lines after -- or __)
    for separator in ["\n--\n", "\n__\n", "\n-- \n"]:
        if separator in body:
            body = body.split(separator)[0].strip()

    result["text"] = body
    return result


def load_email_feedback(uploaded_file) -> pd.DataFrame:
    """
    Load feedback from an uploaded .eml or .txt email file.
    Supports:
    - Single .eml file (one email)
    - .txt file with multiple emails separated by '---'
    Returns a standardised DataFrame.
    """
    rows = []

    try:
        content = uploaded_file.read().decode("utf-8", errors="ignore")

        # Split multiple emails if separated by ---
        emails = content.split("\n---\n") if "\n---\n" in content else [content]

        for raw_email in emails:
            if not raw_email.strip():
                continue

            parsed = parse_email_text(raw_email)
            text   = parsed["text"].strip()

            if len(text) < 10:
                continue

            rows.append({
                "review_id": str(uuid.uuid4()),
                "source":    "Email",
                "date":      parsed["date"],
                "rating":    3,               # No rating in emails — default neutral
                "text":      text,
                "thumbs_up": 0,
                "subject":   parsed["subject"],
                "sender":    parsed["sender"],
            })

    except Exception as e:
        st.error(f"Email parsing error: {e}")

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── SECTION 8d: COMPETITOR BENCHMARKING ──────────────────────

def fetch_competitor_reviews(
    competitor_app_id: str,
    country: str = "us",
    count: int = 100,
) -> pd.DataFrame:
    """Fetch competitor app reviews from Google Play for benchmarking."""
    if not GOOGLE_PLAY_AVAILABLE:
        st.error("google-play-scraper not installed.")
        return pd.DataFrame()
    try:
        result, _ = gp_reviews(
            competitor_app_id,
            lang="en", country=country,
            sort=Sort.NEWEST, count=count,
        )
        rows = []
        for r in result:
            at       = r.get("at", datetime.datetime.now())
            date_obj = at.date() if hasattr(at, "date") else datetime.date.today()
            rows.append({
                "review_id": str(r.get("reviewId", uuid.uuid4())),
                "source":    "Competitor",
                "date":      date_obj,
                "rating":    int(r.get("score", 3)),
                "text":      r.get("content", ""),
                "thumbs_up": r.get("thumbsUpCount", 0),
            })
        if not rows:
            st.warning(f"No reviews found for '{competitor_app_id}'. Try a different app ID.")
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Competitor fetch error: {e}")
        st.info("Try these working IDs: com.google.android.apps.youtube.music | com.amazon.mp3 | com.soundcloud.android")
        return pd.DataFrame()


def build_benchmark_comparison(
    your_df: pd.DataFrame,
    comp_df: pd.DataFrame,
    your_name: str = "Your App",
    comp_name: str = "Competitor",
) -> dict:
    """
    Compare sentiment and ratings between your app and a competitor.
    Returns a dict of comparison metrics and chart figures.
    """
    def _metrics(df, name):
        if df.empty:
            return {}
        total = len(df)
        return {
            "name":        name,
            "total":       total,
            "avg_rating":  round(df["rating"].mean(), 2),
            "positive_pct": round((df["sentiment_label"] == "positive").sum() / total * 100, 1)
                            if "sentiment_label" in df.columns else 0,
            "negative_pct": round((df["sentiment_label"] == "negative").sum() / total * 100, 1)
                            if "sentiment_label" in df.columns else 0,
            "neutral_pct":  round((df["sentiment_label"] == "neutral").sum() / total * 100, 1)
                            if "sentiment_label" in df.columns else 0,
        }

    your_m = _metrics(your_df,  your_name)
    comp_m = _metrics(comp_df,  comp_name)

    # Rating comparison bar chart
    rating_fig = go.Figure()
    for name, df in [(your_name, your_df), (comp_name, comp_df)]:
        if df.empty:
            continue
        counts = df["rating"].value_counts().sort_index()
        rating_fig.add_trace(go.Bar(
            name=name, x=[f"{r}★" for r in counts.index],
            y=counts.values, text=counts.values, textposition="auto",
        ))
    rating_fig.update_layout(
        title="Rating Distribution Comparison",
        barmode="group", template=CHART_TEMPLATE, height=350,
    )

    # Sentiment comparison radar
    if "sentiment_label" in your_df.columns and not comp_df.empty and "sentiment_label" in comp_df.columns:
        categories = ["Positive %", "Neutral %", "Negative %"]
        radar_fig  = go.Figure()
        for m, color in [(your_m, "#3498db"), (comp_m, "#e74c3c")]:
            if not m:
                continue
            radar_fig.add_trace(go.Scatterpolar(
                r=[m.get("positive_pct", 0), m.get("neutral_pct", 0), m.get("negative_pct", 0)],
                theta=categories, fill="toself", name=m["name"],
                line_color=color,
            ))
        radar_fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="Sentiment Comparison", template=CHART_TEMPLATE, height=380,
        )
    else:
        radar_fig = None

    return {
        "your_metrics": your_m,
        "comp_metrics": comp_m,
        "rating_fig":   rating_fig,
        "radar_fig":    radar_fig,
    }


# ── SECTION 8e: CUSTOMER SEGMENTATION ────────────────────────

def segment_customers(df: pd.DataFrame) -> dict:
    """
    Segment reviewers into meaningful groups based on rating + sentiment.
    Returns dict of segment DataFrames and a summary chart.
    """
    if df.empty:
        return {}

    df = df.copy()

    # Define segments
    conditions = [
        (df["rating"] >= 4) & (df.get("sentiment_label", pd.Series(["neutral"]*len(df))) == "positive"),
        (df["rating"] == 5),
        (df["rating"] <= 2) & (df.get("sentiment_label", pd.Series(["neutral"]*len(df))) == "negative"),
        (df["rating"] == 1),
        (df["rating"] == 3),
    ]
    labels = ["Loyal Advocates", "Champions", "At-Risk Users", "Churned Users", "Neutral Users"]

    df["segment"] = "Neutral Users"
    for cond, label in zip(conditions, labels):
        df.loc[cond, "segment"] = label

    # Count per segment
    seg_counts = df["segment"].value_counts().reset_index()
    seg_counts.columns = ["segment", "count"]

    seg_colors = {
        "Champions":       "#27ae60",
        "Loyal Advocates": "#2ecc71",
        "Neutral Users":   "#f39c12",
        "At-Risk Users":   "#e67e22",
        "Churned Users":   "#e74c3c",
    }

    # Donut chart
    seg_fig = go.Figure(go.Pie(
        labels=seg_counts["segment"],
        values=seg_counts["count"],
        hole=0.5,
        marker_colors=[seg_colors.get(s, "#95a5a6") for s in seg_counts["segment"]],
    ))
    seg_fig.update_layout(
        title="Customer Segments",
        template=CHART_TEMPLATE, height=380,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )

    # Avg rating per segment bar
    seg_rating = df.groupby("segment")["rating"].mean().reset_index()
    seg_rating.columns = ["segment", "avg_rating"]
    seg_rating["avg_rating"] = seg_rating["avg_rating"].round(2)

    rating_fig = go.Figure(go.Bar(
        x=seg_rating["segment"],
        y=seg_rating["avg_rating"],
        marker_color=[seg_colors.get(s, "#95a5a6") for s in seg_rating["segment"]],
        text=seg_rating["avg_rating"],
        textposition="auto",
    ))
    rating_fig.update_layout(
        title="Average Rating by Segment",
        xaxis_title="Segment", yaxis_title="Avg Rating",
        template=CHART_TEMPLATE, height=320,
    )

    # Sample reviews per segment
    samples = {}
    for seg in df["segment"].unique():
        seg_df = df[df["segment"] == seg]
        samples[seg] = seg_df.head(3)[["text", "rating", "date", "source"]].to_dict("records")

    return {
        "df":          df,
        "counts":      seg_counts,
        "seg_fig":     seg_fig,
        "rating_fig":  rating_fig,
        "samples":     samples,
        "seg_colors":  seg_colors,
    }


# ── SECTION 8f: ROI CALCULATOR ────────────────────────────────

def calculate_roi(
    df: pd.DataFrame,
    issues_df: pd.DataFrame,
    monthly_active_users: int = 100000,
    avg_revenue_per_user: float = 9.99,
    fix_cost_per_issue:   float = 5000.0,
) -> dict:
    """
    Estimate the business ROI of fixing top critical issues.
    Based on:
    - % negative users who might convert to positive after fix
    - Revenue impact of improved ratings
    - Cost of fixing each issue
    """
    if df.empty or issues_df.empty:
        return {}

    total        = len(df)
    neg_count    = (df["sentiment_label"] == "negative").sum() if "sentiment_label" in df.columns else 0
    neg_pct      = neg_count / max(total, 1)
    current_rating = round(df["rating"].mean(), 2)

    results = []
    critical_issues = issues_df[issues_df["priority"] == "Critical"].head(5)

    for _, row in critical_issues.iterrows():
        freq         = row.get("frequency", 1)
        issue_pct    = freq / max(total, 1)

        # Estimate: fixing this issue converts ~30% of affected negative users
        users_affected      = int(monthly_active_users * neg_pct * issue_pct)
        users_converted     = int(users_affected * 0.30)
        revenue_gain        = round(users_converted * avg_revenue_per_user, 2)
        rating_improvement  = round(issue_pct * 0.5, 3)   # small bump per issue fixed
        net_roi             = round(revenue_gain - fix_cost_per_issue, 2)
        roi_pct             = round((net_roi / max(fix_cost_per_issue, 1)) * 100, 1)

        results.append({
            "issue":             row["issue"].title(),
            "priority":          row["priority"],
            "users_affected":    users_affected,
            "users_converted":   users_converted,
            "revenue_gain":      f"${revenue_gain:,.2f}",
            "fix_cost":          f"${fix_cost_per_issue:,.2f}",
            "net_roi":           f"${net_roi:,.2f}",
            "roi_pct":           f"{roi_pct}%",
            "rating_improvement":f"+{rating_improvement}",
        })

    roi_df = pd.DataFrame(results)

    # ROI bar chart
    if not roi_df.empty:
        roi_fig = go.Figure(go.Bar(
            x=roi_df["issue"],
            y=[float(r.replace("$","").replace(",","")) for r in roi_df["net_roi"]],
            marker_color=["#2ecc71" if float(r.replace("$","").replace(",","")) > 0
                          else "#e74c3c" for r in roi_df["net_roi"]],
            text=roi_df["net_roi"], textposition="auto",
        ))
        roi_fig.update_layout(
            title="Estimated Net ROI per Issue Fixed",
            xaxis_title="Issue", yaxis_title="Net ROI (USD)",
            template=CHART_TEMPLATE, height=350,
        )
    else:
        roi_fig = None

    total_revenue_gain = sum(
        float(r["revenue_gain"].replace("$","").replace(",","")) for r in results
    )
    total_net_roi      = sum(
        float(r["net_roi"].replace("$","").replace(",","")) for r in results
    )

    return {
        "roi_df":              roi_df,
        "roi_fig":             roi_fig,
        "current_rating":      current_rating,
        "total_revenue_gain":  f"${total_revenue_gain:,.2f}",
        "total_net_roi":       f"${total_net_roi:,.2f}",
        "monthly_active_users": monthly_active_users,
    }


# ── SECTION 9: CHART BUILDERS ────────────────────────────────

def chart_sentiment_donut(df: pd.DataFrame) -> go.Figure:
    counts = df["sentiment_label"].value_counts().reset_index()
    counts.columns = ["sentiment", "count"]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=counts["sentiment"],
                values=counts["count"],
                hole=0.5,
                marker_colors=[SENTIMENT_COLORS.get(s, "#95a5a6") for s in counts["sentiment"]],
            )
        ]
    )
    fig.update_layout(
        title="Sentiment Distribution",
        template=CHART_TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        height=350,
    )
    return fig


def chart_sentiment_trend(daily_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=daily_df["date"], y=daily_df["avg_sentiment"],
            mode="markers", name="Daily Sentiment",
            marker=dict(color="#3498db", size=4), opacity=0.5,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=daily_df["date"], y=daily_df["rolling_sentiment"],
            mode="lines", name="7-Day Rolling Avg",
            line=dict(color="#e74c3c", width=2),
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        title="Sentiment Trend Over Time",
        xaxis_title="Date", yaxis_title="Sentiment Score (-1 to 1)",
        template=CHART_TEMPLATE, height=350,
    )
    return fig


def chart_rating_distribution(df: pd.DataFrame) -> go.Figure:
    counts = df["rating"].value_counts().sort_index().reset_index()
    counts.columns = ["rating", "count"]
    colors = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#27ae60"]

    fig = go.Figure(
        data=[
            go.Bar(
                x=(counts["rating"].astype(str) + " ⭐"),
                y=counts["count"],
                marker_color=colors[: len(counts)],
                text=counts["count"],
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title="Rating Distribution", xaxis_title="Rating",
        yaxis_title="Count", template=CHART_TEMPLATE, height=350,
    )
    return fig


def chart_volume_over_time(daily_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for col, name, color in [
        ("positive_count", "Positive", "#2ecc71"),
        ("neutral_count",  "Neutral",  "#f39c12"),
        ("negative_count", "Negative", "#e74c3c"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=daily_df["date"], y=daily_df[col],
                fill="tonexty", mode="lines",
                name=name, line=dict(color=color), stackgroup="one",
            )
        )
    fig.update_layout(
        title="Review Volume Over Time", xaxis_title="Date",
        yaxis_title="Review Count", template=CHART_TEMPLATE, height=350,
    )
    return fig


def chart_wordcloud(df: pd.DataFrame, sentiment_filter: str = "negative") -> plt.Figure:
    filtered = df[df["sentiment_label"] == sentiment_filter]
    fig, ax  = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("#1e1e2e")
    ax.set_facecolor("#1e1e2e")

    if filtered.empty:
        ax.text(0.5, 0.5, f"No {sentiment_filter} reviews found",
                ha="center", va="center", fontsize=14, color="white")
        ax.axis("off")
        return fig

    text = " ".join(filtered["text"].tolist())
    stopwords = {
        "the","and","is","it","this","that","with","have","from","they",
        "will","been","were","when","what","your","more","some","app","just",
    }
    wc = WordCloud(
        width=800, height=400,
        background_color="#1e1e2e",
        colormap="RdYlGn" if sentiment_filter == "positive" else "Reds",
        stopwords=stopwords, max_words=100,
    ).generate(text)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    plt.tight_layout(pad=0)
    return fig


def chart_source_breakdown(df: pd.DataFrame) -> go.Figure:
    ss = df.groupby(["source", "sentiment_label"]).size().reset_index(name="count")
    fig = px.bar(
        ss, x="count", y="source", color="sentiment_label",
        orientation="h", color_discrete_map=SENTIMENT_COLORS,
        title="Reviews by Source & Sentiment", template=CHART_TEMPLATE,
    )
    fig.update_layout(height=300, legend_title="Sentiment")
    return fig


# ── SECTION 9: PDF REPORT GENERATOR ─────────────────────────

def sanitize_pdf_text(text: str) -> str:
    """Remove characters not supported by FPDF Helvetica (latin-1 only)."""
    return text.encode("latin-1", errors="ignore").decode("latin-1")


class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(52, 152, 219)
        self.cell(0, 10, "Feedback Analyser", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(52, 152, 219)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(
            0, 10,
            f"Page {self.page_no()} | Generated: {datetime.date.today()}",
            align="C",
        )


def _fig_to_bytes(fig: go.Figure) -> bytes:
    return fig.to_image(format="png", width=700, height=300, scale=1.5)


def build_pdf_report(
    df: pd.DataFrame,
    daily_df: pd.DataFrame,
    issues_df: pd.DataFrame,
    wow: dict,
    spikes: list,
    date_range: tuple,
) -> bytes:
    """Assemble the full PDF report and return raw bytes."""
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Cover Page ──────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(52, 152, 219)
    pdf.ln(20)
    pdf.cell(0, 15, "Weekly Feedback Report", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(200, 200, 200)
    pdf.cell(0, 10, f"{date_range[0]}  to  {date_range[1]}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    total     = len(df)
    pos_pct   = round((df["sentiment_label"] == "positive").sum() / max(total, 1) * 100, 1)
    neg_pct   = round((df["sentiment_label"] == "negative").sum() / max(total, 1) * 100, 1)
    avg_rating = round(df["rating"].mean(), 2) if total else 0

    for label, value in [
        ("Total Reviews",      str(total)),
        ("Positive Sentiment", f"{pos_pct}%"),
        ("Negative Sentiment", f"{neg_pct}%"),
        ("Average Rating",     f"{avg_rating} / 5"),
    ]:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(80, 8, label + ":", new_x="RIGHT", new_y="LAST")
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(52, 152, 219)
        pdf.cell(60, 8, value, new_x="LMARGIN", new_y="NEXT")

    # ── Executive Summary ────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(52, 152, 219)
    pdf.cell(0, 10, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    points = [
        f"Total of {total} reviews analysed across {df['source'].nunique()} source(s).",
        f"Overall sentiment: {pos_pct}% positive, {neg_pct}% negative.",
        f"Average app rating: {avg_rating}/5 stars.",
        wow.get("message", "Trend data not available."),
        (
            f"{len(spikes)} sentiment spike(s) detected during this period."
            if spikes
            else "No major sentiment spikes detected."
        ),
    ]

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(220, 220, 220)
    for pt in points:
        pdf.set_x(10)
        pdf.multi_cell(190, 8, sanitize_pdf_text("- " + pt))

    # ── Charts Page ──────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(52, 152, 219)
    pdf.set_x(10)
    pdf.cell(0, 10, "Sentiment Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    try:
        pdf.image(BytesIO(_fig_to_bytes(chart_sentiment_donut(df))), x=10, w=90)
    except Exception:
        pass
    try:
        pdf.image(BytesIO(_fig_to_bytes(chart_rating_distribution(df))), x=110, y=pdf.get_y() - 55, w=90)
    except Exception:
        pass

    pdf.set_x(10)
    pdf.ln(5)

    if not daily_df.empty:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(52, 152, 219)
        pdf.set_x(10)
        pdf.cell(0, 10, "Sentiment Trend", new_x="LMARGIN", new_y="NEXT")
        try:
            pdf.image(BytesIO(_fig_to_bytes(chart_sentiment_trend(daily_df))), x=10, w=190)
        except Exception:
            pass
        pdf.set_x(10)

    # ── Issues Table ─────────────────────────────────────────
    if not issues_df.empty:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(52, 152, 219)
        pdf.set_x(10)
        pdf.cell(0, 10, "Top Critical Issues", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        for tier_label, tier_filter in [("Critical Issues", "Critical"), ("Moderate Issues", "Moderate")]:
            tier_df = issues_df[issues_df["priority"] == tier_filter].head(5)
            if tier_df.empty:
                continue

            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(220, 220, 220)
            pdf.set_x(10)
            pdf.cell(0, 8, tier_label, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            # Header
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(52, 73, 94)
            pdf.set_text_color(255, 255, 255)
            pdf.set_x(10)
            for hdr, w in [("Issue", 60), ("Frequency", 30), ("Recent 7d", 30), ("Sample Quote", 70)]:
                pdf.cell(w, 7, hdr, border=1, fill=True, new_x="RIGHT", new_y="LAST")
            pdf.ln()

            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(200, 200, 200)
            for _, row in tier_df.iterrows():
                quote = sanitize_pdf_text(str(row.get("sample_quote", ""))[:55])
                pdf.set_x(10)
                for val, w in [
                    (sanitize_pdf_text(str(row["issue"]).title()),    60),
                    (str(row["frequency"]),                            30),
                    (str(row.get("recent_count", 0)),                  30),
                    (quote,                                            70),
                ]:
                    pdf.cell(w, 7, val, border=1, new_x="RIGHT", new_y="LAST")
                pdf.ln()
            pdf.ln(5)

    # ── Recommendations ──────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(52, 152, 219)
    pdf.set_x(10)
    pdf.cell(0, 10, "Recommendations", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    recs = []
    if not issues_df.empty:
        for issue in issues_df[issues_df["priority"] == "Critical"]["issue"].head(3):
            recs.append(f"Immediately investigate reports related to '{issue}' - flagged critical.")
    if neg_pct > 40:
        recs.append("High negative sentiment (>40%). Consider an emergency bug-review cycle.")
    if spikes:
        recs.append(f"Review {len(spikes)} spike(s) for root-cause analysis.")
    if wow.get("direction") == "declining":
        recs.append("Sentiment declining WoW. Prioritise user-feedback review in sprint planning.")
    if not recs:
        recs = [
            "Continue monitoring feedback trends.",
            "Maintain current support response times.",
            "Consider proactive outreach to low-rating reviewers.",
        ]

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(220, 220, 220)
    for i, rec in enumerate(recs, 1):
        pdf.set_x(10)
        pdf.multi_cell(190, 8, sanitize_pdf_text(f"{i}. {rec}"))
        pdf.ln(1)

    return bytes(pdf.output())


# ── SECTION 10: STREAMLIT UI ─────────────────────────────────

def main():
    # Page config
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT,
        initial_sidebar_state="expanded",
    )

    # Custom CSS
    st.markdown(
        """
        <style>
        .main { background-color: #0e1117; }
        .metric-card {
            background: linear-gradient(135deg,#1e1e2e,#2d2d44);
            border-radius:12px; padding:20px;
            border-left:4px solid #3498db; margin-bottom:10px;
        }
        div[data-testid="stMetricValue"]{ font-size:2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Header
    st.title(f"{PAGE_ICON} {APP_TITLE}")
    st.caption("Real-time app-review monitoring · Sentiment analysis · Automated reporting")
    st.divider()

    # ── Sidebar ─────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuration")

        st.subheader("📱 App Settings")
        play_app_id   = st.text_input("Google Play App ID",  value=DEFAULT_PLAY_APP_ID,
                                       help="e.g. com.spotify.music")
        app_store_id  = st.text_input("App Store App ID",    value=DEFAULT_APP_STORE_ID,
                                       help="Numeric ID from App Store URL")
        country       = st.selectbox("Country", ["us", "gb", "in", "au", "ca"])
        review_count  = st.slider("Reviews to fetch (per source)", 50, 500, 200, 50)

        st.divider()
        st.subheader("📁 CSV Upload")
        csv_file = st.file_uploader(
            "Upload review CSV", type=["csv"],
            help="Columns: text/review, date (optional), rating (optional)",
        )

        st.divider()
        st.subheader("📧 Email Upload")
        email_file = st.file_uploader(
            "Upload .eml or .txt email file",
            type=["eml", "txt"],
            help="Plain text emails or .eml files. Separate multiple emails with '---'",
        )

        st.divider()
        st.subheader("🤖 AI Insights (Groq)")
        # Loads automatically from .env file
        GROQ_API_KEY_DEFAULT = os.getenv("GROQ_API_KEY", "")
        groq_api_key = st.text_input(
            "Groq API Key",
            value=GROQ_API_KEY_DEFAULT,
            type="password",
            help="Free key at https://console.groq.com",
        )

        st.divider()
        st.subheader("🏆 Competitor Benchmarking")
        competitor_app_id = st.text_input(
            "Competitor Play App ID",
            value="com.apple.music",
            help="e.g. com.apple.music or com.soundcloud.android",
        )
        competitor_name = st.text_input("Competitor Name", value="Apple Music")

        st.divider()
        st.subheader("🔍 Filters")
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("From", value=datetime.date.today() - datetime.timedelta(days=30))
        with c2:
            end_date   = st.date_input("To",   value=datetime.date.today())

        selected_sources = st.multiselect(
            "Sources", ["Google Play", "App Store", "CSV"],
            default=["Google Play", "App Store", "CSV"],
        )
        selected_sentiments = st.multiselect(
            "Sentiment", ["positive", "neutral", "negative"],
            default=["positive", "neutral", "negative"],
        )
        min_rating = st.slider("Minimum Rating", 1, 5, 1)

        st.divider()
        fetch_btn = st.button("🚀 Fetch & Analyse", type="primary", use_container_width=True)
        demo_btn  = st.button("🎮 Load Demo Data",  use_container_width=True,
                               help="Load sample data instantly without fetching live reviews")

        st.divider()
        st.subheader("⚙️ Advanced")
        auto_refresh = st.checkbox("Auto-refresh every 5 min", value=False)

    # ── Session State ────────────────────────────────────────
    for key, default in [
        ("df",         pd.DataFrame()),
        ("daily_df",   pd.DataFrame()),
        ("issues_df",  pd.DataFrame()),
        ("wow",        {}),
        ("spikes",     []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Demo Mode ────────────────────────────────────────────
    if demo_btn:
        with st.spinner("Loading demo data…"):
            demo_df = generate_demo_data()
            daily_df  = calculate_daily_sentiment(demo_df)
            wow       = calculate_week_over_week(daily_df)
            spikes    = detect_spikes(daily_df)
            issues_df = score_issues(demo_df)
            if not issues_df.empty:
                issues_df = assign_priority(issues_df)
            st.session_state.df        = demo_df
            st.session_state.daily_df  = daily_df
            st.session_state.issues_df = issues_df
            st.session_state.wow       = wow
            st.session_state.spikes    = spikes
        st.success("🎮 Demo data loaded! 150 sample reviews ready to explore.")

    # ── Fetch & Analyse ──────────────────────────────────────
    if fetch_btn:
        dfs = []

        if "Google Play" in selected_sources:
            with st.status("Fetching Google Play reviews…"):
                gp_df = fetch_google_play_reviews(play_app_id, country, DEFAULT_LANG, review_count)
                if not gp_df.empty:
                    st.success(f"✅ Fetched {len(gp_df)} Play Store reviews")
                    dfs.append(gp_df)
                else:
                    st.warning("⚠️ No Play Store reviews fetched")

        if "App Store" in selected_sources:
            with st.status("Fetching App Store reviews…"):
                as_df = fetch_app_store_reviews(app_store_id, country)
                if not as_df.empty:
                    st.success(f"✅ Fetched {len(as_df)} App Store reviews")
                    dfs.append(as_df)
                else:
                    st.warning("⚠️ No App Store reviews fetched")

        if csv_file and "CSV" in selected_sources:
            with st.status("Loading CSV reviews…"):
                csv_df = load_csv_reviews(csv_file)
                if not csv_df.empty:
                    st.success(f"✅ Loaded {len(csv_df)} CSV reviews")
                    dfs.append(csv_df)

        if email_file:
            with st.status("Parsing email feedback…"):
                email_df = load_email_feedback(email_file)
                if not email_df.empty:
                    st.success(f"✅ Parsed {len(email_df)} email(s) as feedback")
                    dfs.append(email_df)
                else:
                    st.warning("⚠️ No feedback found in email file")

        if not dfs:
            st.error("❌ No reviews fetched. Check your app IDs or upload a CSV.")
            return

        with st.spinner("Preprocessing…"):
            combined = standardize_reviews(dfs)

        if combined.empty:
            st.error("❌ No valid reviews after preprocessing.")
            return

        model    = load_sentiment_model()
        combined = run_sentiment_analysis(combined, model)
        combined = extract_keywords(combined)

        daily_df   = calculate_daily_sentiment(combined)
        wow        = calculate_week_over_week(daily_df)
        spikes     = detect_spikes(daily_df)
        issues_df  = score_issues(combined)
        if not issues_df.empty:
            issues_df = assign_priority(issues_df)

        st.session_state.df        = combined
        st.session_state.daily_df  = daily_df
        st.session_state.issues_df = issues_df
        st.session_state.wow       = wow
        st.session_state.spikes    = spikes

        st.success(f"✅ Analysis complete! {len(combined):,} reviews processed.")
        st.balloons()

    # ── Load from session ────────────────────────────────────
    df         = st.session_state.df
    daily_df   = st.session_state.daily_df
    issues_df  = st.session_state.issues_df
    wow        = st.session_state.wow
    spikes     = st.session_state.spikes

    if df.empty:
        st.info("👈 Configure your app IDs in the sidebar and click **Fetch & Analyse** to get started.")
        for title, body in [
            ("📱 Multi-Source",  "Aggregate reviews from Google Play, App Store & CSV surveys"),
            ("🧠 AI Sentiment",  "Powered by transformer models for accurate sentiment classification"),
            ("📊 Smart Reports", "Auto-generate professional PDF reports with charts and insights"),
        ]:
            st.markdown(
                f'<div class="metric-card"><h3>{title}</h3><p>{body}</p></div>',
                unsafe_allow_html=True,
            )
        return

    # Apply sidebar filters
    filtered_df = df[
        (df["date"] >= start_date)
        & (df["date"] <= end_date)
        & (df["source"].isin(selected_sources))
        & (df["sentiment_label"].isin(selected_sentiments))
        & (df["rating"] >= min_rating)
    ].copy()

    if filtered_df.empty:
        st.warning("No reviews match the current filters. Adjust the sidebar filters.")
        return

    filtered_daily = calculate_daily_sentiment(filtered_df)

    # ── Sentiment Alerts Banner ───────────────────────────────
    alerts = check_sentiment_alerts(filtered_daily)
    for alert in alerts:
        if alert["level"] == "CRITICAL":
            st.error(f"🚨 ALERT: {alert['message']}")
        else:
            st.warning(f"⚠️ ALERT: {alert['message']}")

    # ── Auto Refresh ──────────────────────────────────────────
    if auto_refresh:
        st.info("🔄 Auto-refresh enabled. Page refreshes every 5 minutes.")
        time.sleep(300)
        st.rerun()

    # ── Tabs ─────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📊 Overview", "📈 Trends",    "🔮 Predictions",
        "🚨 Issues",   "📋 All Reviews","🌍 Languages",
        "🏆 Benchmark","👥 Segments",  "💰 ROI",
        "📄 Reports",
    ])

    # ════════════════════════════════════════════════════════
    # TAB 1 — OVERVIEW
    # ════════════════════════════════════════════════════════
    with tab1:
        st.subheader("📊 Overview Dashboard")

        total      = len(filtered_df)
        pos_count  = (filtered_df["sentiment_label"] == "positive").sum()
        neg_count  = (filtered_df["sentiment_label"] == "negative").sum()
        avg_rating = round(filtered_df["rating"].mean(), 2)
        pos_pct    = round(pos_count / total * 100, 1)
        neg_pct    = round(neg_count / total * 100, 1)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Reviews",  f"{total:,}")
        m2.metric("Avg Rating",     f"{avg_rating} ⭐")
        m3.metric("Positive",       f"{pos_pct}%",  delta=f"{pos_count} reviews")
        m4.metric("Negative",       f"{neg_pct}%",  delta=f"{neg_count} reviews", delta_color="inverse")
        m5.metric("Sources",        filtered_df["source"].nunique())
        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(chart_sentiment_donut(filtered_df),     use_container_width=True, key="overview_donut")
        with c2:
            st.plotly_chart(chart_rating_distribution(filtered_df), use_container_width=True, key="overview_rating_dist")

        c3, c4 = st.columns(2)
        with c3:
            st.plotly_chart(chart_source_breakdown(filtered_df),    use_container_width=True, key="overview_source")
        with c4:
            if not filtered_daily.empty:
                st.plotly_chart(chart_volume_over_time(filtered_daily), use_container_width=True, key="overview_volume")

        st.subheader("🕐 Recent Reviews")
        for _, row in filtered_df.sort_values("date", ascending=False).head(5).iterrows():
            icon = "✅" if row["sentiment_label"] == "positive" else (
                "❌" if row["sentiment_label"] == "negative" else "➖"
            )
            with st.expander(
                f"{icon} {row['source']} — {'⭐' * int(row['rating'])} — {row['date']}"
            ):
                st.write(row["text"])

        # ── AI Insights (Groq) ───────────────────────────────
        st.divider()
        st.subheader("🤖 AI-Generated Insights")
        if groq_api_key:
            if st.button("✨ Generate AI Insights", type="secondary"):
                with st.spinner("Asking Llama3 via Groq…"):
                    insight = groq_ai_insight(
                        issues_df, filtered_df, wow, groq_api_key
                    )
                if insight and not insight.startswith("Groq") and not insight.startswith("AI insight"):
                    st.success("AI Insight generated!")
                    st.markdown(
                        f"""
                        <div style='background:linear-gradient(135deg,#1e1e2e,#2d2d44);
                        border-radius:12px;padding:20px;border-left:4px solid #9b59b6;'>
                        <h4 style='color:#9b59b6;margin:0 0 10px 0;'>Llama3 Analysis</h4>
                        <p style='color:#ddd;line-height:1.6;margin:0;'>{insight}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.warning(insight or "No insight returned. Check your API key.")
        else:
            st.info("💡 Add your free **Groq API key** in the sidebar to enable AI-generated insights powered by Llama3.")

    # ════════════════════════════════════════════════════════
    # TAB 2 — TRENDS
    # ════════════════════════════════════════════════════════
    with tab2:
        st.subheader("📈 Trend Analysis")

        # Use full daily_df for WoW — not filtered (filtered may be too short)
        trend_daily = daily_df if not daily_df.empty else filtered_daily
        trend_wow   = calculate_week_over_week(trend_daily)
        trend_spikes = detect_spikes(trend_daily)

        if trend_daily.empty:
            st.info("Not enough data to display trends.")
        else:
            if trend_wow:
                icon_map = {"improving": "🟢", "declining": "🔴", "stable": "🟡"}
                st.info(f"{icon_map.get(trend_wow.get('direction','stable'), '➡️')} {trend_wow.get('message','')}")

            if trend_spikes:
                st.error(f"⚠️ {len(trend_spikes)} sentiment spike(s) detected!")
                for sp in trend_spikes:
                    st.warning(
                        f"📅 {sp['date']}: {sp['negative_count']} negative reviews "
                        f"(Z-score: {sp['z_score']})"
                    )

            st.plotly_chart(chart_sentiment_trend(trend_daily),  use_container_width=True, key="trends_sentiment")
            st.plotly_chart(chart_volume_over_time(trend_daily), use_container_width=True, key="trends_volume")

            st.subheader("📅 Weekly Breakdown")
            if "week" in df.columns:
                weekly = (
                    df.groupby("week")
                    .agg(
                        total      = ("review_id",       "count"),
                        avg_rating = ("rating",          "mean"),
                        positive   = ("sentiment_label", lambda x: (x == "positive").sum()),
                        negative   = ("sentiment_label", lambda x: (x == "negative").sum()),
                    )
                    .reset_index()
                )
                weekly["avg_rating"] = weekly["avg_rating"].round(2)
                weekly["pos_pct"]    = (weekly["positive"] / weekly["total"] * 100).round(1).astype(str) + "%"
                weekly["neg_pct"]    = (weekly["negative"] / weekly["total"] * 100).round(1).astype(str) + "%"
                st.dataframe(
                    weekly[["week", "total", "avg_rating", "pos_pct", "neg_pct"]],
                    use_container_width=True,
                )

    # ════════════════════════════════════════════════════════
    # TAB 3 — PREDICTIONS (BONUS)
    # ════════════════════════════════════════════════════════
    with tab3:
        st.subheader("🔮 Predictive Analytics — 14-Day Forecast")

        # Use full daily_df (not filtered) for better prediction data
        pred_daily = daily_df if len(daily_df) >= 3 else filtered_daily

        if pred_daily.empty or len(pred_daily) < 3:
            st.info("Need at least 3 days of data to generate predictions. Click 🎮 Load Demo Data in sidebar.")
        else:
            pred_df = predict_sentiment_trend(pred_daily, days_ahead=14)

            if not pred_df.empty:
                direction = "improving" if pred_df["predicted_sentiment"].iloc[-1] > pred_daily["rolling_sentiment"].iloc[-1] else "declining"
                dir_icon  = "📈" if direction == "improving" else "📉"
                st.info(f"{dir_icon} Forecast shows sentiment **{direction}** over the next 14 days.")

            st.plotly_chart(chart_prediction(pred_daily, pred_df), use_container_width=True, key="pred_chart")

            if not pred_df.empty:
                st.subheader("📅 Forecast Table")
                pred_display = pred_df.copy()
                pred_display["date"]                = pred_display["date"].dt.strftime("%Y-%m-%d")
                pred_display["predicted_sentiment"] = pred_display["predicted_sentiment"].round(3)
                pred_display["outlook"] = pred_display["predicted_sentiment"].apply(
                    lambda x: "Positive" if x > 0.1 else ("Negative" if x < -0.1 else "Neutral")
                )
                st.dataframe(pred_display, use_container_width=True)

            st.divider()
            st.subheader("📊 Rating Forecast")
            st.caption("Projected average rating based on current trend")

            if not pred_daily.empty:
                avg_now  = pred_daily["avg_rating"].mean()
                sentiment_change = pred_df["predicted_sentiment"].mean() - pred_daily["rolling_sentiment"].mean() if not pred_df.empty else 0
                projected_rating = round(min(5.0, max(1.0, avg_now + sentiment_change)), 2)

                r1, r2, r3 = st.columns(3)
                r1.metric("Current Avg Rating",   f"{round(avg_now, 2)} ⭐")
                r2.metric("Projected Rating",      f"{projected_rating} ⭐",
                          delta=f"{round(projected_rating - avg_now, 2)}")
                r3.metric("Forecast Confidence",   "Medium" if len(pred_daily) >= 14 else "Low",
                          help="Based on amount of historical data available")

    # ════════════════════════════════════════════════════════
    # TAB 4 — ISSUES
    # ════════════════════════════════════════════════════════
    with tab4:
        st.subheader("🚨 Issue Prioritisation")

        if issues_df.empty:
            st.info("No issues detected. Run analysis first or there may be insufficient negative reviews.")
        else:
            priority_filter = st.multiselect(
                "Filter by Priority", ["Critical", "Moderate", "Low"],
                default=["Critical", "Moderate"],
            )
            filtered_issues = issues_df[issues_df["priority"].isin(priority_filter)]

            for _, row in filtered_issues.head(10).iterrows():
                pri   = row["priority"]
                icon  = "🔴" if pri == "Critical" else ("🟡" if pri == "Moderate" else "🟢")
                with st.expander(
                    f"{icon} **{row['issue'].title()}** — {pri} "
                    f"| Freq: {row['frequency']} | Recent 7d: {row.get('recent_count', 0)}"
                ):
                    ca, cb = st.columns(2)
                    with ca:
                        st.metric("Frequency",     row["frequency"])
                        st.metric("Recent (7d)",   row.get("recent_count", 0))
                    with cb:
                        st.metric("Neg Score",     round(row["avg_sentiment_score"], 3))
                        st.metric("Total Reviews", row.get("total_reviews", 0))

                    st.markdown("**Sample Quote:**")
                    st.markdown(f"> _{row.get('sample_quote', 'N/A')}_")

                    extra_quotes = get_sample_quotes(filtered_df, row["issue"])
                    if len(extra_quotes) > 1:
                        st.markdown("**More Reviews:**")
                        for q in extra_quotes[1:]:
                            st.markdown(
                                f"- _{q['text'][:150]}…_ ({q['source']}, {q['date']})"
                            )

                    # AI suggested response
                    if groq_api_key and row.get("sample_quote"):
                        if st.button(f"🤖 Suggest Response", key=f"suggest_{row['issue']}"):
                            with st.spinner("Generating response suggestion…"):
                                suggestion = groq_suggest_response(
                                    str(row["sample_quote"]), groq_api_key
                                )
                            if suggestion:
                                st.info(f"💬 **Suggested Reply:** {suggestion}")

            st.divider()
            st.subheader("📊 Issues Priority Summary")
            if not issues_df.empty:
                priority_counts = issues_df["priority"].value_counts().reset_index()
                priority_counts.columns = ["priority", "count"]
                pfig = go.Figure(go.Bar(
                    x=priority_counts["priority"],
                    y=priority_counts["count"],
                    marker_color=[PRIORITY_COLORS.get(p, "#95a5a6") for p in priority_counts["priority"]],
                    text=priority_counts["count"],
                    textposition="auto",
                ))
                pfig.update_layout(title="Issues by Priority Tier", template=CHART_TEMPLATE, height=300)
                st.plotly_chart(pfig, use_container_width=True, key="issues_priority_bar")

        st.divider()
        st.subheader("☁️ Word Cloud")
        wc_sentiment = st.radio("Word Cloud For:", ["negative", "positive", "neutral"], horizontal=True)
        wc_fig = chart_wordcloud(filtered_df, wc_sentiment)
        st.pyplot(wc_fig, use_container_width=True)
        plt.close()

    # ════════════════════════════════════════════════════════
    # TAB 5 — ALL REVIEWS
    # ════════════════════════════════════════════════════════
    with tab5:
        st.subheader("📋 All Reviews")

        search_query = st.text_input("🔍 Search reviews", placeholder="Type keyword to filter…")
        display_df   = filtered_df.copy()

        if search_query:
            display_df = display_df[
                display_df["text"].str.lower().str.contains(search_query.lower(), na=False)
            ]

        sc, so = st.columns(2)
        with sc:
            sort_by = st.selectbox("Sort by", ["date", "rating", "sentiment_score"])
        with so:
            asc = st.radio("Order", ["Descending", "Ascending"], horizontal=True) == "Ascending"

        display_df = display_df.sort_values(sort_by, ascending=asc)
        st.caption(f"Showing {len(display_df):,} reviews")

        show_cols = [c for c in ["date", "source", "rating", "sentiment_label", "sentiment_score", "text"]
                     if c in display_df.columns]

        st.dataframe(
            display_df[show_cols].head(500),
            use_container_width=True,
            column_config={
                "rating":          st.column_config.NumberColumn("Rating ⭐", min_value=1, max_value=5),
                "sentiment_label": st.column_config.TextColumn("Sentiment"),
                "sentiment_score": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
                "text":            st.column_config.TextColumn("Review Text", width="large"),
                "date":            st.column_config.DateColumn("Date"),
                "source":          st.column_config.TextColumn("Source"),
            },
        )

        csv_export = display_df[show_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Filtered Reviews (CSV)",
            data=csv_export,
            file_name=f"reviews_export_{datetime.date.today()}.csv",
            mime="text/csv",
        )

    # ════════════════════════════════════════════════════════
    # TAB 6 — LANGUAGES (BONUS)
    # ════════════════════════════════════════════════════════
    with tab6:
        st.subheader("🌍 Multi-Language Analysis")
        st.caption("Detects language distribution across all reviews")

        lang_df = detect_language_distribution(filtered_df)

        if not lang_df.empty:
            l1, l2 = st.columns(2)
            with l1:
                lfig = go.Figure(go.Bar(
                    x=lang_df["count"],
                    y=lang_df["language"],
                    orientation="h",
                    marker_color="#3498db",
                    text=lang_df["count"],
                    textposition="auto",
                ))
                lfig.update_layout(
                    title="Reviews by Detected Language",
                    template=CHART_TEMPLATE, height=350,
                )
                st.plotly_chart(lfig, use_container_width=True, key="lang_bar")

            with l2:
                lfig2 = go.Figure(go.Pie(
                    labels=lang_df["language"],
                    values=lang_df["count"],
                    hole=0.4,
                ))
                lfig2.update_layout(
                    title="Language Share",
                    template=CHART_TEMPLATE, height=350,
                )
                st.plotly_chart(lfig2, use_container_width=True, key="lang_pie")

            st.subheader("📊 Sentiment by Language")
            merged = filtered_df.copy()
            merged["language"] = "English"
            lang_patterns = {
                "Spanish": r"\b(que|el|la|de|en|es)\b",
                "French":  r"\b(le|la|les|de|et|en)\b",
                "German":  r"\b(die|der|das|und|ist)\b",
                "Hindi":   r"[\u0900-\u097F]",
                "Japanese":r"[\u3040-\u309F]",
                "Korean":  r"[\uAC00-\uD7AF]",
                "Chinese": r"[\u4E00-\u9FFF]",
            }
            for lang, pattern in lang_patterns.items():
                mask = merged["text"].str.contains(pattern, regex=True, na=False)
                merged.loc[mask, "language"] = lang

            lang_sent = (
                merged.groupby(["language", "sentiment_label"])
                .size().reset_index(name="count")
            )
            if not lang_sent.empty:
                lsfig = px.bar(
                    lang_sent, x="language", y="count",
                    color="sentiment_label",
                    color_discrete_map=SENTIMENT_COLORS,
                    title="Sentiment Distribution per Language",
                    template=CHART_TEMPLATE,
                )
                st.plotly_chart(lsfig, use_container_width=True, key="lang_sentiment")

            st.dataframe(lang_df, use_container_width=True)

    # ════════════════════════════════════════════════════════
    # TAB 7 — COMPETITOR BENCHMARKING (BONUS)
    # ════════════════════════════════════════════════════════
    with tab7:
        st.subheader("🏆 Competitor Benchmarking")
        st.caption("Compare your app's sentiment and ratings vs a competitor")

        your_app_name = play_app_id.split(".")[-1].title() if play_app_id else "Your App"

        if st.button("🔍 Fetch Competitor Reviews & Compare", type="primary"):
            with st.spinner(f"Fetching {competitor_name} reviews…"):
                comp_raw = fetch_competitor_reviews(competitor_app_id, country, 100)

            if comp_raw.empty:
                st.warning("Could not fetch competitor reviews. Check the app ID.")
            else:
                with st.spinner("Running sentiment analysis on competitor reviews…"):
                    model    = load_sentiment_model()
                    comp_std = standardize_reviews([comp_raw])
                    comp_std = run_sentiment_analysis(comp_std, model)

                bench = build_benchmark_comparison(
                    filtered_df, comp_std, your_app_name, competitor_name
                )

                ym = bench["your_metrics"]
                cm = bench["comp_metrics"]

                st.subheader("📊 Head-to-Head Comparison")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Your Avg Rating",    f"{ym.get('avg_rating','N/A')} ⭐",
                          delta=f"{round(ym.get('avg_rating',0) - cm.get('avg_rating',0), 2)} vs competitor")
                c2.metric("Competitor Rating",  f"{cm.get('avg_rating','N/A')} ⭐")
                c3.metric("Your Positive %",    f"{ym.get('positive_pct','N/A')}%",
                          delta=f"{round(ym.get('positive_pct',0) - cm.get('positive_pct',0), 1)}%")
                c4.metric("Competitor Positive %", f"{cm.get('positive_pct','N/A')}%")

                st.plotly_chart(bench["rating_fig"], use_container_width=True, key="bench_rating")
                if bench["radar_fig"]:
                    st.plotly_chart(bench["radar_fig"], use_container_width=True, key="bench_radar")

                # Winner callout
                if ym.get("avg_rating", 0) > cm.get("avg_rating", 0):
                    st.success(f"🏆 {your_app_name} leads with higher avg rating!")
                elif ym.get("avg_rating", 0) < cm.get("avg_rating", 0):
                    st.warning(f"⚠️ {competitor_name} has a higher avg rating. Focus on critical issues!")
                else:
                    st.info("🤝 Both apps are rated equally.")
        else:
            st.info(f"Configure competitor app ID in the sidebar, then click the button above.")
            st.markdown(f"""
            **Popular competitor IDs:**
            - Apple Music: `com.apple.music`
            - YouTube Music: `com.google.android.apps.youtube.music`
            - Amazon Music: `com.amazon.mp3`
            - SoundCloud: `com.soundcloud.android`
            - Deezer: `deezer.android.app`
            """)

    # ════════════════════════════════════════════════════════
    # TAB 8 — CUSTOMER SEGMENTATION (BONUS)
    # ════════════════════════════════════════════════════════
    with tab8:
        st.subheader("👥 Customer Segmentation")
        st.caption("Understand who your reviewers are and how to engage them")

        segs = segment_customers(filtered_df)

        if not segs:
            st.info("No data for segmentation. Fetch reviews first.")
        else:
            counts = segs["counts"]
            total  = counts["count"].sum()

            # Metrics row
            seg_cols = st.columns(len(counts))
            for i, (_, row) in enumerate(counts.iterrows()):
                color = segs["seg_colors"].get(row["segment"], "#95a5a6")
                seg_cols[i].metric(
                    row["segment"],
                    f"{row['count']}",
                    f"{round(row['count']/total*100,1)}%",
                )

            st.divider()

            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(segs["seg_fig"],    use_container_width=True, key="seg_donut")
            with c2:
                st.plotly_chart(segs["rating_fig"], use_container_width=True, key="seg_rating")

            st.subheader("🎯 Engagement Strategy per Segment")
            strategies = {
                "Champions":       "🟢 **Champions** — Ask for App Store reviews. Offer beta access. They are your best advocates.",
                "Loyal Advocates": "🟢 **Loyal Advocates** — Send thank-you messages. Offer loyalty rewards.",
                "Neutral Users":   "🟡 **Neutral Users** — Survey them. Find what would make them love the app.",
                "At-Risk Users":   "🟠 **At-Risk Users** — Proactive outreach. Offer support. Address their complaint.",
                "Churned Users":   "🔴 **Churned Users** — Win-back campaign. Fix their reported issue. Direct support contact.",
            }
            for seg, strategy in strategies.items():
                count = counts[counts["segment"] == seg]["count"].sum()
                if count > 0:
                    st.markdown(strategy)

            st.divider()
            st.subheader("📝 Sample Reviews by Segment")
            selected_seg = st.selectbox("View reviews for segment:", list(segs["samples"].keys()))
            for review in segs["samples"].get(selected_seg, []):
                st.markdown(
                    f"> _{review['text'][:200]}_  \n"
                    f"**Rating:** {'⭐' * int(review['rating'])} | "
                    f"**Source:** {review['source']} | **Date:** {review['date']}"
                )
                st.divider()

    # ════════════════════════════════════════════════════════
    # TAB 9 — ROI CALCULATOR (BONUS)
    # ════════════════════════════════════════════════════════
    with tab9:
        st.subheader("💰 ROI Calculator")
        st.caption("Estimate revenue impact of fixing critical issues")

        if issues_df.empty:
            st.info("No issues detected yet. Fetch and analyse reviews first.")
        else:
            st.subheader("⚙️ Business Parameters")
            r1, r2, r3 = st.columns(3)
            with r1:
                mau = st.number_input(
                    "Monthly Active Users", min_value=1000,
                    max_value=100_000_000, value=100_000, step=10_000,
                )
            with r2:
                arpu = st.number_input(
                    "Avg Revenue / User ($)", min_value=0.0,
                    max_value=100.0, value=9.99, step=0.01,
                )
            with r3:
                fix_cost = st.number_input(
                    "Fix Cost / Issue ($)", min_value=0.0,
                    max_value=1_000_000.0, value=5000.0, step=500.0,
                )

            roi_data = calculate_roi(
                filtered_df, issues_df,
                monthly_active_users=int(mau),
                avg_revenue_per_user=float(arpu),
                fix_cost_per_issue=float(fix_cost),
            )

            if roi_data:
                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("Current Avg Rating",   f"{roi_data['current_rating']} ⭐")
                m2.metric("Total Revenue Potential", roi_data["total_revenue_gain"])
                m3.metric("Total Net ROI",         roi_data["total_net_roi"],
                          delta="after fixing all critical issues")

                if roi_data["roi_fig"]:
                    st.plotly_chart(roi_data["roi_fig"], use_container_width=True, key="roi_bar")

                st.subheader("📊 Issue-by-Issue ROI Breakdown")
                if not roi_data["roi_df"].empty:
                    st.dataframe(
                        roi_data["roi_df"],
                        use_container_width=True,
                        column_config={
                            "issue":             st.column_config.TextColumn("Issue"),
                            "priority":          st.column_config.TextColumn("Priority"),
                            "users_affected":    st.column_config.NumberColumn("Users Affected"),
                            "users_converted":   st.column_config.NumberColumn("Est. Converted"),
                            "revenue_gain":      st.column_config.TextColumn("Revenue Gain"),
                            "fix_cost":          st.column_config.TextColumn("Fix Cost"),
                            "net_roi":           st.column_config.TextColumn("Net ROI"),
                            "roi_pct":           st.column_config.TextColumn("ROI %"),
                            "rating_improvement":st.column_config.TextColumn("Rating Boost"),
                        },
                    )

                st.info(
                    "💡 **Methodology:** Estimates assume fixing each issue converts ~30% of "
                    "affected negative users to satisfied users. Adjust parameters above to match "
                    "your business reality."
                )

    # ════════════════════════════════════════════════════════
    # TAB 10 — REPORTS
    # ════════════════════════════════════════════════════════
    with tab10:
        st.subheader("📄 Weekly Report Generator")
        st.markdown(
            """
            Generate a professional PDF report containing:
            - Sentiment overview with charts
            - Sentiment trend and week-over-week analysis
            - Top critical issues with sample quotes
            - Actionable recommendations
            """
        )

        r1, r2 = st.columns(2)
        with r1:
            rep_start = st.date_input("Report Start", value=datetime.date.today() - datetime.timedelta(days=7))
        with r2:
            rep_end   = st.date_input("Report End",   value=datetime.date.today())

        if st.button("📊 Generate PDF Report", type="primary"):
            rep_df = df[(df["date"] >= rep_start) & (df["date"] <= rep_end)].copy()

            if rep_df.empty:
                st.warning("No reviews in the selected date range for the report.")
            else:
                with st.spinner("Generating PDF report…"):
                    try:
                        rep_daily  = calculate_daily_sentiment(rep_df)
                        rep_wow    = calculate_week_over_week(rep_daily)
                        rep_spikes = detect_spikes(rep_daily)
                        rep_issues = score_issues(rep_df)
                        if not rep_issues.empty:
                            rep_issues = assign_priority(rep_issues)

                        pdf_bytes = build_pdf_report(
                            rep_df, rep_daily, rep_issues,
                            rep_wow, rep_spikes, (rep_start, rep_end),
                        )
                        st.success("✅ Report generated successfully!")

                        pr1, pr2, pr3 = st.columns(3)
                        pr1.metric("Reviews in Report", len(rep_df))
                        pr2.metric("Positive", f"{round((rep_df['sentiment_label']=='positive').sum()/len(rep_df)*100,1)}%")
                        pr3.metric("Negative", f"{round((rep_df['sentiment_label']=='negative').sum()/len(rep_df)*100,1)}%")

                        st.download_button(
                            "⬇️ Download PDF Report",
                            data=pdf_bytes,
                            file_name=f"feedback_report_{rep_start}_to_{rep_end}.pdf",
                            mime="application/pdf",
                        )

                    except Exception as e:
                        st.error(f"Report generation failed: {e}")
                        st.code(traceback.format_exc())


# ── ENTRY POINT ──────────────────────────────────────────────
if __name__ == "__main__":
    main()