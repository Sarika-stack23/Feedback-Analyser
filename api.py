# ============================================================
# Feedback Analyser — api.py
# FastAPI REST API with OpenAPI/Swagger documentation
# Run: uvicorn api:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs
# ============================================================

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import datetime
import uuid
import io
import pandas as pd

# Import core logic from main.py
from main import (
    fetch_google_play_reviews,
    fetch_app_store_reviews,
    load_csv_reviews,
    standardize_reviews,
    run_sentiment_analysis,
    extract_keywords,
    calculate_daily_sentiment,
    calculate_week_over_week,
    detect_spikes,
    score_issues,
    assign_priority,
    build_pdf_report,
    load_sentiment_model,
)
from database import (
    SessionLocal,
    ReviewModel,
    AnalysisJobModel,
    save_reviews_to_db,
    get_reviews_from_db,
    save_job,
    update_job_status,
)

# ── App Setup ────────────────────────────────────────────────
app = FastAPI(
    title="Feedback Analyser API",
    description="""
## Feedback Analyser REST API

A complete API for analysing app store reviews and customer feedback.

### Features
- **Fetch Reviews** from Google Play Store and Apple App Store
- **Upload CSV** feedback files for analysis
- **Sentiment Analysis** using HuggingFace transformer models
- **Trend Detection** with week-over-week comparisons
- **Issue Prioritisation** — Critical / Moderate / Low tiers
- **PDF Reports** — downloadable weekly summaries

### Quick Start
1. `POST /reviews/fetch` — fetch reviews from app stores
2. `GET /reviews` — list all stored reviews
3. `GET /analytics/summary` — get sentiment overview
4. `GET /analytics/issues` — get prioritised issues
5. `GET /reports/pdf` — download PDF report
""",
    version="1.0.0",
    contact={
        "name":  "Feedback Analyser",
        "email": "support@feedbackanalyser.com",
    },
    license_info={
        "name": "MIT",
    },
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models (Request / Response Schemas) ─────────────

class FetchRequest(BaseModel):
    play_app_id:   str             = Field("com.spotify.music", description="Google Play app package name")
    app_store_id:  str             = Field("324684580",         description="Apple App Store numeric app ID")
    country:       str             = Field("us",                description="Country code (us, gb, in, etc.)")
    review_count:  int             = Field(100,                 description="Number of reviews to fetch per source", ge=10, le=500)
    sources:       List[str]       = Field(["google_play", "app_store"], description="Sources to fetch from")


class ReviewOut(BaseModel):
    review_id:       str
    source:          str
    date:            str
    rating:          int
    text:            str
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None

    class Config:
        from_attributes = True


class SummaryOut(BaseModel):
    total_reviews:    int
    positive_count:   int
    negative_count:   int
    neutral_count:    int
    positive_pct:     float
    negative_pct:     float
    neutral_pct:      float
    avg_rating:       float
    sources:          List[str]
    date_range_start: str
    date_range_end:   str


class TrendOut(BaseModel):
    direction:   str
    change_pct:  float
    message:     str
    spikes:      List[dict]


class IssueOut(BaseModel):
    issue:               str
    priority:            str
    frequency:           int
    recent_count:        int
    avg_sentiment_score: float
    sample_quote:        str


class JobOut(BaseModel):
    job_id:    str
    status:    str
    message:   str
    created_at: str


class HealthOut(BaseModel):
    status:  str
    version: str
    time:    str


# ── Helpers ───────────────────────────────────────────────────

def _load_and_analyse(dfs: list) -> pd.DataFrame:
    """Standardise + run sentiment on a list of raw dataframes."""
    combined = standardize_reviews(dfs)
    if combined.empty:
        return combined
    model    = load_sentiment_model()
    combined = run_sentiment_analysis(combined, model)
    combined = extract_keywords(combined)
    return combined


def _df_to_review_list(df: pd.DataFrame) -> List[dict]:
    reviews = []
    for _, row in df.iterrows():
        reviews.append({
            "review_id":       str(row.get("review_id", uuid.uuid4())),
            "source":          str(row.get("source", "")),
            "date":            str(row.get("date", "")),
            "rating":          int(row.get("rating", 3)),
            "text":            str(row.get("text", "")),
            "sentiment_label": str(row.get("sentiment_label", "")),
            "sentiment_score": float(row.get("sentiment_score", 0.0)),
        })
    return reviews


# ── Routes ────────────────────────────────────────────────────

@app.get("/", tags=["Health"], response_model=HealthOut, summary="API Health Check")
def root():
    """Check if the API is running."""
    return {
        "status":  "healthy",
        "version": "1.0.0",
        "time":    datetime.datetime.now().isoformat(),
    }


@app.get("/health", tags=["Health"], response_model=HealthOut, summary="Health Check")
def health():
    """Detailed health check endpoint."""
    return {
        "status":  "healthy",
        "version": "1.0.0",
        "time":    datetime.datetime.now().isoformat(),
    }


# ── Reviews Endpoints ─────────────────────────────────────────

@app.post(
    "/reviews/fetch",
    tags=["Reviews"],
    summary="Fetch reviews from app stores",
    response_model=JobOut,
)
def fetch_reviews(request: FetchRequest, background_tasks: BackgroundTasks):
    """
    Fetch reviews from Google Play Store and/or Apple App Store.

    - **play_app_id**: Google Play app package name (e.g. `com.spotify.music`)
    - **app_store_id**: App Store numeric ID (e.g. `324684580`)
    - **country**: Country code for localised reviews
    - **review_count**: Number of reviews per source (10–500)
    - **sources**: List of sources to fetch from
    """
    job_id = str(uuid.uuid4())
    db     = SessionLocal()

    try:
        save_job(db, job_id, "running", "Fetching reviews…")

        def run_fetch():
            inner_db = SessionLocal()
            try:
                dfs = []
                if "google_play" in request.sources:
                    gp = fetch_google_play_reviews(
                        request.play_app_id, request.country, "en", request.review_count
                    )
                    if not gp.empty:
                        dfs.append(gp)

                if "app_store" in request.sources:
                    ap = fetch_app_store_reviews(request.app_store_id, request.country)
                    if not ap.empty:
                        dfs.append(ap)

                if not dfs:
                    update_job_status(inner_db, job_id, "failed", "No reviews fetched.")
                    return

                combined = _load_and_analyse(dfs)
                if combined.empty:
                    update_job_status(inner_db, job_id, "failed", "Preprocessing returned no reviews.")
                    return

                save_reviews_to_db(inner_db, combined)
                update_job_status(
                    inner_db, job_id, "completed",
                    f"Fetched and analysed {len(combined)} reviews."
                )
            except Exception as e:
                update_job_status(inner_db, job_id, "failed", str(e))
            finally:
                inner_db.close()

        background_tasks.add_task(run_fetch)

        return {
            "job_id":    job_id,
            "status":    "running",
            "message":   "Fetch job started in background. Poll /jobs/{job_id} for status.",
            "created_at": datetime.datetime.now().isoformat(),
        }

    finally:
        db.close()


@app.post(
    "/reviews/upload",
    tags=["Reviews"],
    summary="Upload CSV file of reviews",
)
async def upload_csv(file: UploadFile = File(..., description="CSV file with review data")):
    """
    Upload a CSV file containing reviews for analysis.

    Expected columns:
    - `text` or `review` or `comment` — review text (required)
    - `date` — review date (optional)
    - `rating` — star rating 1-5 (optional)
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    contents = await file.read()
    df_raw   = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    csv_df   = load_csv_reviews(io.StringIO(contents.decode("utf-8")))

    if csv_df.empty:
        raise HTTPException(status_code=422, detail="Could not parse CSV. Ensure it has a text/review column.")

    combined = _load_and_analyse([csv_df])
    db       = SessionLocal()
    try:
        save_reviews_to_db(db, combined)
    finally:
        db.close()

    return {
        "message":        f"Successfully uploaded and analysed {len(combined)} reviews.",
        "total_uploaded": len(combined),
        "columns_found":  list(df_raw.columns),
    }


@app.get(
    "/reviews",
    tags=["Reviews"],
    summary="List all stored reviews",
)
def list_reviews(
    source:    Optional[str] = Query(None, description="Filter by source (Google Play, App Store, CSV)"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment (positive, neutral, negative)"),
    min_rating:int            = Query(1,    description="Minimum star rating", ge=1, le=5),
    limit:     int            = Query(100,  description="Max results to return", ge=1, le=1000),
    offset:    int            = Query(0,    description="Pagination offset", ge=0),
):
    """
    Retrieve stored reviews with optional filters.

    - Filter by **source**, **sentiment**, **rating**
    - Supports **pagination** via limit/offset
    """
    db = SessionLocal()
    try:
        reviews = get_reviews_from_db(db, source, sentiment, min_rating, limit, offset)
        return {
            "total":   len(reviews),
            "offset":  offset,
            "limit":   limit,
            "reviews": reviews,
        }
    finally:
        db.close()


@app.get(
    "/reviews/{review_id}",
    tags=["Reviews"],
    summary="Get a single review by ID",
)
def get_review(review_id: str):
    """Retrieve a specific review by its unique ID."""
    db = SessionLocal()
    try:
        review = db.query(ReviewModel).filter(ReviewModel.review_id == review_id).first()
        if not review:
            raise HTTPException(status_code=404, detail=f"Review {review_id} not found.")
        return {
            "review_id":       review.review_id,
            "source":          review.source,
            "date":            str(review.date),
            "rating":          review.rating,
            "text":            review.text,
            "sentiment_label": review.sentiment_label,
            "sentiment_score": review.sentiment_score,
        }
    finally:
        db.close()


# ── Analytics Endpoints ───────────────────────────────────────

@app.get(
    "/analytics/summary",
    tags=["Analytics"],
    summary="Get sentiment summary",
    response_model=SummaryOut,
)
def analytics_summary(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date:   Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    source:     Optional[str] = Query(None, description="Filter by source"),
):
    """
    Get an overall sentiment summary of all stored reviews.

    Returns counts, percentages, average rating, and date range.
    """
    db = SessionLocal()
    try:
        reviews = get_reviews_from_db(db, source=source, limit=10000)
        if not reviews:
            raise HTTPException(status_code=404, detail="No reviews found. Fetch reviews first.")

        df = pd.DataFrame(reviews)
        df["date"] = pd.to_datetime(df["date"])

        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        if df.empty:
            raise HTTPException(status_code=404, detail="No reviews in the specified date range.")

        total    = len(df)
        pos      = int((df["sentiment_label"] == "positive").sum())
        neg      = int((df["sentiment_label"] == "negative").sum())
        neu      = int((df["sentiment_label"] == "neutral").sum())

        return {
            "total_reviews":    total,
            "positive_count":   pos,
            "negative_count":   neg,
            "neutral_count":    neu,
            "positive_pct":     round(pos / total * 100, 1),
            "negative_pct":     round(neg / total * 100, 1),
            "neutral_pct":      round(neu / total * 100, 1),
            "avg_rating":       round(df["rating"].mean(), 2),
            "sources":          df["source"].unique().tolist(),
            "date_range_start": str(df["date"].min().date()),
            "date_range_end":   str(df["date"].max().date()),
        }
    finally:
        db.close()


@app.get(
    "/analytics/trends",
    tags=["Analytics"],
    summary="Get sentiment trends",
    response_model=TrendOut,
)
def analytics_trends(
    source: Optional[str] = Query(None, description="Filter by source"),
):
    """
    Get sentiment trend analysis including week-over-week comparison and spike detection.
    """
    db = SessionLocal()
    try:
        reviews = get_reviews_from_db(db, source=source, limit=10000)
        if not reviews:
            raise HTTPException(status_code=404, detail="No reviews found.")

        df        = pd.DataFrame(reviews)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["sentiment_label"] = df.get("sentiment_label", pd.Series(["neutral"] * len(df)))

        daily_df  = calculate_daily_sentiment(df)
        wow       = calculate_week_over_week(daily_df)
        spikes    = detect_spikes(daily_df)

        return {
            "direction":  wow.get("direction", "stable"),
            "change_pct": wow.get("change", 0),
            "message":    wow.get("message", ""),
            "spikes":     spikes[:5],
        }
    finally:
        db.close()


@app.get(
    "/analytics/issues",
    tags=["Analytics"],
    summary="Get prioritised issues",
)
def analytics_issues(
    priority: Optional[str] = Query(None, description="Filter: Critical, Moderate, Low"),
    limit:    int            = Query(20,   description="Max issues to return", ge=1, le=100),
):
    """
    Get a ranked list of issues detected from negative reviews.

    Issues are prioritised as **Critical**, **Moderate**, or **Low** based on
    frequency, sentiment score, and recency.
    """
    db = SessionLocal()
    try:
        reviews = get_reviews_from_db(db, sentiment="negative", limit=5000)
        if not reviews:
            return {"total": 0, "issues": []}

        df = pd.DataFrame(reviews)
        df["date"]            = pd.to_datetime(df["date"]).dt.date
        df["sentiment_label"] = "negative"
        df["keywords"]        = df["text"].apply(lambda t: str(t).lower().split()[:4])

        issues_df = score_issues(df)
        if issues_df.empty:
            return {"total": 0, "issues": []}

        issues_df = assign_priority(issues_df)
        if priority:
            issues_df = issues_df[issues_df["priority"] == priority]

        return {
            "total":  len(issues_df),
            "issues": issues_df.head(limit).to_dict(orient="records"),
        }
    finally:
        db.close()


@app.get(
    "/analytics/daily",
    tags=["Analytics"],
    summary="Get daily sentiment metrics",
)
def analytics_daily(
    days: int = Query(30, description="Number of past days to include", ge=1, le=365),
):
    """
    Get day-by-day sentiment metrics for charting trend graphs.
    """
    db = SessionLocal()
    try:
        reviews = get_reviews_from_db(db, limit=10000)
        if not reviews:
            raise HTTPException(status_code=404, detail="No reviews found.")

        df            = pd.DataFrame(reviews)
        df["date"]    = pd.to_datetime(df["date"]).dt.date
        cutoff        = datetime.date.today() - datetime.timedelta(days=days)
        df            = df[df["date"] >= cutoff]

        daily_df      = calculate_daily_sentiment(df)
        daily_df["date"] = daily_df["date"].astype(str)

        return {
            "days":   days,
            "total":  len(daily_df),
            "data":   daily_df.to_dict(orient="records"),
        }
    finally:
        db.close()


# ── Reports Endpoints ─────────────────────────────────────────

@app.get(
    "/reports/pdf",
    tags=["Reports"],
    summary="Download PDF report",
    response_class=StreamingResponse,
)
def download_pdf_report(
    start_date: str = Query(..., description="Report start date YYYY-MM-DD"),
    end_date:   str = Query(..., description="Report end date YYYY-MM-DD"),
):
    """
    Generate and download a professional PDF report for the specified date range.

    The report includes:
    - Executive summary with key metrics
    - Sentiment overview charts
    - Sentiment trend analysis
    - Top critical issues table
    - Actionable recommendations
    """
    db = SessionLocal()
    try:
        reviews = get_reviews_from_db(db, limit=10000)
        if not reviews:
            raise HTTPException(status_code=404, detail="No reviews found. Fetch reviews first.")

        df         = pd.DataFrame(reviews)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        start      = datetime.date.fromisoformat(start_date)
        end        = datetime.date.fromisoformat(end_date)
        rep_df     = df[(df["date"] >= start) & (df["date"] <= end)].copy()

        if rep_df.empty:
            raise HTTPException(status_code=404, detail="No reviews in the specified date range.")

        daily_df   = calculate_daily_sentiment(rep_df)
        wow        = calculate_week_over_week(daily_df)
        spikes     = detect_spikes(daily_df)
        issues_df  = score_issues(rep_df)
        if not issues_df.empty:
            issues_df = assign_priority(issues_df)

        pdf_bytes  = build_pdf_report(rep_df, daily_df, issues_df, wow, spikes, (start, end))

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=feedback_report_{start_date}_to_{end_date}.pdf"
            },
        )
    finally:
        db.close()


# ── Jobs Endpoints ────────────────────────────────────────────

@app.get(
    "/jobs/{job_id}",
    tags=["Jobs"],
    summary="Check background job status",
    response_model=JobOut,
)
def get_job_status(job_id: str):
    """
    Poll the status of a background fetch job.

    Status values: `running`, `completed`, `failed`
    """
    db = SessionLocal()
    try:
        job = db.query(AnalysisJobModel).filter(AnalysisJobModel.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
        return {
            "job_id":    job.job_id,
            "status":    job.status,
            "message":   job.message,
            "created_at": str(job.created_at),
        }
    finally:
        db.close()