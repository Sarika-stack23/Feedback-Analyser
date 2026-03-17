# ============================================================
# Feedback Analyser — Test Suite
# Run: pytest tests.py -v --tb=short
# ============================================================

import pytest
import datetime
import pandas as pd
import numpy as np
import sys
import os

# Add parent directory so we can import from main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    clean_text,
    standardize_reviews,
    rating_to_sentiment,
    calculate_daily_sentiment,
    calculate_week_over_week,
    detect_spikes,
    score_issues,
    assign_priority,
    sanitize_pdf_text,
)


# ── FIXTURES ─────────────────────────────────────────────────

@pytest.fixture
def sample_reviews_df():
    """A small unified reviews dataframe for testing."""
    today = datetime.date.today()
    return pd.DataFrame([
        {
            "review_id":       "r001",
            "source":          "Google Play",
            "date":            today - datetime.timedelta(days=i),
            "rating":          rating,
            "text":            text,
            "thumbs_up":       0,
            "sentiment_label": sentiment,
            "sentiment_score": score,
            "keywords":        keywords,
        }
        for i, (rating, text, sentiment, score, keywords) in enumerate([
            (5, "Amazing app love it great features works perfectly", "positive", 0.95, ["amazing", "great features"]),
            (1, "App keeps crashing terrible bug broken unusable crash", "negative", 0.92, ["crashing", "bug", "broken"]),
            (3, "Average app nothing special decent okay", "neutral", 0.70, ["average", "decent"]),
            (2, "Too many ads premium popups very annoying cannot listen", "negative", 0.88, ["ads", "premium"]),
            (5, "Best music app ever recommend to everyone perfect", "positive", 0.97, ["best", "recommend"]),
            (1, "Login broken cannot access account lost playlists", "negative", 0.90, ["login", "broken", "account"]),
            (4, "Good app clean UI easy to use smooth performance", "positive", 0.82, ["good", "clean", "easy"]),
            (1, "Constant buffering slow streaming quality terrible wifi", "negative", 0.91, ["buffering", "streaming", "terrible"]),
            (5, "Love personalized recommendations discover weekly perfect", "positive", 0.94, ["recommendations", "discover"]),
            (2, "Battery drain heats phone terrible performance drains fast", "negative", 0.86, ["battery", "drain", "performance"]),
        ])
    ])


@pytest.fixture
def sample_raw_df():
    """Raw reviews before sentiment analysis."""
    today = datetime.date.today()
    return pd.DataFrame([
        {"review_id": "r1", "source": "Google Play", "date": today, "rating": 5,
         "text": "Great app love it", "thumbs_up": 10},
        {"review_id": "r2", "source": "App Store",   "date": today, "rating": 1,
         "text": "Crashes all the time terrible", "thumbs_up": 0},
        {"review_id": "r3", "source": "CSV",          "date": today, "rating": 3,
         "text": "Okay nothing special average", "thumbs_up": 2},
    ])


# ── SECTION 4: PREPROCESSING TESTS ──────────────────────────

class TestCleanText:

    def test_removes_html_tags(self):
        assert "<b>" not in clean_text("<b>Hello</b>")

    def test_removes_urls(self):
        result = clean_text("Visit https://example.com for more info")
        assert "https" not in result

    def test_strips_extra_whitespace(self):
        result = clean_text("too    many     spaces")
        assert "  " not in result

    def test_handles_empty_string(self):
        assert clean_text("") == ""

    def test_handles_none(self):
        assert clean_text(None) == ""

    def test_preserves_normal_text(self):
        result = clean_text("This is normal text.")
        assert "normal text" in result

    def test_removes_special_characters(self):
        result = clean_text("Hello @#$% World")
        assert "@" not in result


class TestStandardizeReviews:

    def test_merges_multiple_dataframes(self, sample_raw_df):
        df1 = sample_raw_df[sample_raw_df["source"] == "Google Play"].copy()
        df2 = sample_raw_df[sample_raw_df["source"] == "App Store"].copy()
        result = standardize_reviews([df1, df2])
        assert len(result) == 2

    def test_returns_empty_for_empty_input(self):
        result = standardize_reviews([])
        assert result.empty

    def test_removes_duplicates(self, sample_raw_df):
        doubled = pd.concat([sample_raw_df, sample_raw_df])
        result  = standardize_reviews([doubled])
        assert len(result) <= len(sample_raw_df)

    def test_has_required_columns(self, sample_raw_df):
        result = standardize_reviews([sample_raw_df])
        for col in ["review_id", "source", "date", "rating", "text"]:
            assert col in result.columns

    def test_rating_clipped_1_to_5(self):
        df = pd.DataFrame([{
            "review_id": "x", "source": "CSV", "date": datetime.date.today(),
            "rating": 10, "text": "some review text here", "thumbs_up": 0,
        }])
        result = standardize_reviews([df])
        if not result.empty:
            assert result["rating"].max() <= 5
            assert result["rating"].min() >= 1

    def test_drops_short_text(self):
        df = pd.DataFrame([{
            "review_id": "x", "source": "CSV", "date": datetime.date.today(),
            "rating": 3, "text": "ok", "thumbs_up": 0,
        }])
        result = standardize_reviews([df])
        assert result.empty


# ── SECTION 5: SENTIMENT TESTS ───────────────────────────────

class TestRatingToSentiment:

    def test_5_star_is_positive(self):
        label, score = rating_to_sentiment(5)
        assert label == "positive"

    def test_4_star_is_positive(self):
        label, score = rating_to_sentiment(4)
        assert label == "positive"

    def test_3_star_is_neutral(self):
        label, score = rating_to_sentiment(3)
        assert label == "neutral"

    def test_2_star_is_negative(self):
        label, score = rating_to_sentiment(2)
        assert label == "negative"

    def test_1_star_is_negative(self):
        label, score = rating_to_sentiment(1)
        assert label == "negative"

    def test_score_is_float(self):
        _, score = rating_to_sentiment(5)
        assert isinstance(score, float)

    def test_score_between_0_and_1(self):
        for rating in [1, 2, 3, 4, 5]:
            _, score = rating_to_sentiment(rating)
            assert 0.0 <= score <= 1.0


# ── SECTION 6: TREND TESTS ───────────────────────────────────

class TestCalculateDailySentiment:

    def test_returns_dataframe(self, sample_reviews_df):
        result = calculate_daily_sentiment(sample_reviews_df)
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self, sample_reviews_df):
        result = calculate_daily_sentiment(sample_reviews_df)
        for col in ["date", "avg_sentiment", "review_count", "rolling_sentiment"]:
            assert col in result.columns

    def test_returns_empty_for_empty_input(self):
        result = calculate_daily_sentiment(pd.DataFrame())
        assert result.empty

    def test_rolling_sentiment_not_null(self, sample_reviews_df):
        result = calculate_daily_sentiment(sample_reviews_df)
        assert result["rolling_sentiment"].notna().all()

    def test_avg_sentiment_range(self, sample_reviews_df):
        result = calculate_daily_sentiment(sample_reviews_df)
        assert result["avg_sentiment"].between(-1, 1).all()


class TestWeekOverWeek:

    def test_returns_dict(self, sample_reviews_df):
        daily = calculate_daily_sentiment(sample_reviews_df)
        result = calculate_week_over_week(daily)
        assert isinstance(result, dict)

    def test_has_required_keys(self, sample_reviews_df):
        daily  = calculate_daily_sentiment(sample_reviews_df)
        result = calculate_week_over_week(daily)
        for key in ["change", "direction", "message"]:
            assert key in result

    def test_direction_valid_values(self, sample_reviews_df):
        daily  = calculate_daily_sentiment(sample_reviews_df)
        result = calculate_week_over_week(daily)
        assert result["direction"] in ["improving", "declining", "stable"]

    def test_insufficient_data_returns_stable(self):
        tiny_df = pd.DataFrame({"date": [datetime.date.today()],
                                 "avg_sentiment": [0.5],
                                 "review_count": [1],
                                 "rolling_sentiment": [0.5],
                                 "positive_count": [1],
                                 "negative_count": [0],
                                 "neutral_count": [0],
                                 "avg_rating": [4.0]})
        result = calculate_week_over_week(tiny_df)
        assert result["direction"] == "stable"


class TestDetectSpikes:

    def test_returns_list(self, sample_reviews_df):
        daily  = calculate_daily_sentiment(sample_reviews_df)
        result = detect_spikes(daily)
        assert isinstance(result, list)

    def test_spike_has_required_keys(self, sample_reviews_df):
        daily = calculate_daily_sentiment(sample_reviews_df)
        spikes = detect_spikes(daily, threshold=0.0)
        if spikes:
            for key in ["date", "negative_count", "z_score"]:
                assert key in spikes[0]

    def test_empty_input_returns_empty(self):
        assert detect_spikes(pd.DataFrame()) == []


# ── SECTION 7: ISSUE PRIORITIZATION TESTS ───────────────────

class TestScoreIssues:

    def test_returns_dataframe(self, sample_reviews_df):
        result = score_issues(sample_reviews_df)
        assert isinstance(result, pd.DataFrame)

    def test_returns_empty_for_empty_input(self):
        assert score_issues(pd.DataFrame()).empty

    def test_has_issue_column(self, sample_reviews_df):
        result = score_issues(sample_reviews_df)
        if not result.empty:
            assert "issue" in result.columns

    def test_has_frequency_column(self, sample_reviews_df):
        result = score_issues(sample_reviews_df)
        if not result.empty:
            assert "frequency" in result.columns


class TestAssignPriority:

    def test_returns_dataframe(self, sample_reviews_df):
        issues = score_issues(sample_reviews_df)
        if not issues.empty:
            result = assign_priority(issues)
            assert isinstance(result, pd.DataFrame)

    def test_priority_values_valid(self, sample_reviews_df):
        issues = score_issues(sample_reviews_df)
        if not issues.empty:
            result = assign_priority(issues)
            assert set(result["priority"].unique()).issubset({"Critical", "Moderate", "Low"})

    def test_sorted_by_score_descending(self, sample_reviews_df):
        issues = score_issues(sample_reviews_df)
        if not issues.empty:
            result = assign_priority(issues)
            scores = result["priority_score"].tolist()
            assert scores == sorted(scores, reverse=True)


# ── PDF SANITIZE TESTS ───────────────────────────────────────

class TestSanitizePdfText:

    def test_removes_bullet_unicode(self):
        result = sanitize_pdf_text("• Hello")
        assert "•" not in result

    def test_removes_emoji(self):
        result = sanitize_pdf_text("Great 🎉")
        assert "🎉" not in result

    def test_keeps_normal_text(self):
        result = sanitize_pdf_text("Hello World 123")
        assert "Hello World 123" == result

    def test_handles_empty_string(self):
        assert sanitize_pdf_text("") == ""


# ── INTEGRATION TEST ─────────────────────────────────────────

class TestEndToEndPipeline:

    def test_full_pipeline_from_csv_data(self):
        """Simulate loading CSV → standardize → sentiment → trends → issues."""
        today = datetime.date.today()
        raw_df = pd.DataFrame([
            {"review_id": str(i), "source": "CSV",
             "date": today - datetime.timedelta(days=i % 14),
             "rating": (i % 5) + 1,
             "text": text, "thumbs_up": 0}
            for i, text in enumerate([
                "Amazing app love all the features works great",
                "Crashes constantly broken terrible unusable app",
                "Okay app average nothing special decent",
                "Too many ads premium annoying cannot listen",
                "Best app ever recommend perfect music streaming",
                "Login broken account lost playlists cannot access",
                "Good clean UI easy navigate smooth performance fast",
                "Buffering slow streaming terrible quality bad wifi",
                "Love recommendations discover weekly playlist perfect",
                "Battery drain heats phone terrible slow performance",
                "Great sound quality excellent audio streaming good",
                "Update broke everything songs skip playlist missing",
                "Excellent customer support resolved issue quickly thanks",
                "Offline download broken cannot save songs anymore fails",
            ])
        ])

        # Step 1: Standardize
        df = standardize_reviews([raw_df])
        assert not df.empty
        assert "text" in df.columns

        # Step 2: Sentiment fallback (no model)
        labels, scores = [], []
        for _, row in df.iterrows():
            l, s = rating_to_sentiment(row["rating"])
            labels.append(l)
            scores.append(s)
        df["sentiment_label"] = labels
        df["sentiment_score"]  = scores

        assert "sentiment_label" in df.columns
        assert set(df["sentiment_label"].unique()).issubset({"positive", "neutral", "negative"})

        # Step 3: Trends
        daily = calculate_daily_sentiment(df)
        assert not daily.empty

        # Step 4: Issues
        df["keywords"] = df["text"].apply(lambda t: t.split()[:3])
        issues = score_issues(df)
        if not issues.empty:
            prioritized = assign_priority(issues)
            assert "priority" in prioritized.columns

        print("Full pipeline test passed!")


# ── MAIN ─────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])