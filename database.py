# ============================================================
# Feedback Analyser — database.py
# SQLAlchemy ORM models + CRUD helpers
# Uses SQLite for local dev, swap DATABASE_URL for PostgreSQL
# ============================================================

import os
import uuid
import datetime
from typing import Optional, List

import pandas as pd
from sqlalchemy import (
    create_engine, Column, String, Integer,
    Float, Date, DateTime, Text, Boolean,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# ── Database URL ─────────────────────────────────────────────
# SQLite for local development (zero setup)
# For PostgreSQL: postgresql://user:password@localhost:5432/feedback_analyser
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./feedback_analyser.db")

engine       = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


# ── ORM Models ───────────────────────────────────────────────

class ReviewModel(Base):
    """Stores individual reviews from all sources."""
    __tablename__ = "reviews"

    id              = Column(Integer,  primary_key=True, index=True, autoincrement=True)
    review_id       = Column(String,   unique=True, index=True, nullable=False)
    source          = Column(String,   index=True, nullable=False)          # Google Play / App Store / CSV
    date            = Column(Date,     index=True, nullable=False)
    rating          = Column(Integer,  nullable=False, default=3)
    text            = Column(Text,     nullable=False)
    thumbs_up       = Column(Integer,  default=0)
    sentiment_label = Column(String,   index=True, nullable=True)           # positive / neutral / negative
    sentiment_score = Column(Float,    nullable=True)                       # 0.0 – 1.0
    keywords        = Column(Text,     nullable=True)                       # JSON string list
    is_flagged      = Column(Boolean,  default=False)                       # Critical flag
    created_at      = Column(DateTime, default=datetime.datetime.utcnow)
    app_id          = Column(String,   nullable=True, index=True)           # e.g. com.spotify.music

    def to_dict(self) -> dict:
        return {
            "review_id":       self.review_id,
            "source":          self.source,
            "date":            str(self.date),
            "rating":          self.rating,
            "text":            self.text,
            "thumbs_up":       self.thumbs_up,
            "sentiment_label": self.sentiment_label,
            "sentiment_score": self.sentiment_score,
            "is_flagged":      self.is_flagged,
            "created_at":      str(self.created_at),
        }


class AnalysisJobModel(Base):
    """Tracks background fetch/analysis jobs."""
    __tablename__ = "analysis_jobs"

    id         = Column(Integer,  primary_key=True, autoincrement=True)
    job_id     = Column(String,   unique=True, index=True, nullable=False)
    status     = Column(String,   nullable=False, default="running")    # running / completed / failed
    message    = Column(Text,     nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class IssueModel(Base):
    """Stores detected and prioritised issues."""
    __tablename__ = "issues"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    issue_keyword        = Column(String,  index=True, nullable=False)
    priority             = Column(String,  index=True, nullable=False)  # Critical / Moderate / Low
    frequency            = Column(Integer, default=0)
    recent_count         = Column(Integer, default=0)
    avg_sentiment_score  = Column(Float,   default=0.0)
    sample_quote         = Column(Text,    nullable=True)
    detected_at          = Column(DateTime, default=datetime.datetime.utcnow)
    app_id               = Column(String,  nullable=True)


class ReportModel(Base):
    """Tracks generated PDF reports."""
    __tablename__ = "reports"

    id           = Column(Integer,  primary_key=True, autoincrement=True)
    report_id    = Column(String,   unique=True, index=True, nullable=False)
    start_date   = Column(Date,     nullable=False)
    end_date     = Column(Date,     nullable=False)
    total_reviews= Column(Integer,  default=0)
    created_at   = Column(DateTime, default=datetime.datetime.utcnow)


# ── Create Tables ─────────────────────────────────────────────

def init_db():
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


# ── CRUD Helpers ──────────────────────────────────────────────

def save_reviews_to_db(db: Session, df: pd.DataFrame, app_id: str = None) -> int:
    """
    Persist a DataFrame of reviews to the database.
    Skips duplicates based on review_id.
    Returns number of new rows inserted.
    """
    if df.empty:
        return 0

    import json
    inserted = 0

    for _, row in df.iterrows():
        rid = str(row.get("review_id", uuid.uuid4()))

        # Skip if already exists
        exists = db.query(ReviewModel).filter(ReviewModel.review_id == rid).first()
        if exists:
            continue

        keywords_val = row.get("keywords", [])
        if isinstance(keywords_val, list):
            keywords_val = json.dumps(keywords_val)

        review = ReviewModel(
            review_id       = rid,
            source          = str(row.get("source", "unknown")),
            date            = row.get("date", datetime.date.today()),
            rating          = int(row.get("rating", 3)),
            text            = str(row.get("text", "")),
            thumbs_up       = int(row.get("thumbs_up", 0)),
            sentiment_label = str(row.get("sentiment_label", "")) or None,
            sentiment_score = float(row.get("sentiment_score", 0.0)) if row.get("sentiment_score") else None,
            keywords        = keywords_val if isinstance(keywords_val, str) else None,
            app_id          = app_id,
        )
        db.add(review)
        inserted += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

    return inserted


def get_reviews_from_db(
    db:         Session,
    source:     Optional[str] = None,
    sentiment:  Optional[str] = None,
    min_rating: int            = 1,
    limit:      int            = 500,
    offset:     int            = 0,
) -> List[dict]:
    """
    Query reviews from the database with optional filters.
    Returns a list of dicts.
    """
    query = db.query(ReviewModel)

    if source:
        query = query.filter(ReviewModel.source == source)
    if sentiment:
        query = query.filter(ReviewModel.sentiment_label == sentiment)
    if min_rating > 1:
        query = query.filter(ReviewModel.rating >= min_rating)

    query = query.order_by(ReviewModel.date.desc())
    query = query.offset(offset).limit(limit)

    return [r.to_dict() for r in query.all()]


def save_job(db: Session, job_id: str, status: str, message: str) -> AnalysisJobModel:
    """Create a new analysis job record."""
    job = AnalysisJobModel(job_id=job_id, status=status, message=message)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_status(db: Session, job_id: str, status: str, message: str):
    """Update the status and message of an existing job."""
    job = db.query(AnalysisJobModel).filter(AnalysisJobModel.job_id == job_id).first()
    if job:
        job.status     = status
        job.message    = message
        job.updated_at = datetime.datetime.utcnow()
        db.commit()


def save_issues_to_db(db: Session, issues_df: pd.DataFrame, app_id: str = None):
    """Persist prioritised issues to the database."""
    if issues_df.empty:
        return
    # Clear old issues for this app
    db.query(IssueModel).filter(IssueModel.app_id == app_id).delete()
    for _, row in issues_df.iterrows():
        issue = IssueModel(
            issue_keyword       = str(row.get("issue", "")),
            priority            = str(row.get("priority", "Low")),
            frequency           = int(row.get("frequency", 0)),
            recent_count        = int(row.get("recent_count", 0)),
            avg_sentiment_score = float(row.get("avg_sentiment_score", 0.0)),
            sample_quote        = str(row.get("sample_quote", ""))[:500],
            app_id              = app_id,
        )
        db.add(issue)
    db.commit()


def get_db_stats(db: Session) -> dict:
    """Return quick statistics about what is stored in the database."""
    total      = db.query(ReviewModel).count()
    by_source  = {}
    by_sentiment = {}

    for source in ["Google Play", "App Store", "CSV"]:
        count = db.query(ReviewModel).filter(ReviewModel.source == source).count()
        if count:
            by_source[source] = count

    for sentiment in ["positive", "neutral", "negative"]:
        count = db.query(ReviewModel).filter(ReviewModel.sentiment_label == sentiment).count()
        if count:
            by_sentiment[sentiment] = count

    return {
        "total_reviews":  total,
        "by_source":      by_source,
        "by_sentiment":   by_sentiment,
        "total_jobs":     db.query(AnalysisJobModel).count(),
        "total_issues":   db.query(IssueModel).count(),
    }


# Initialise DB on import
init_db()