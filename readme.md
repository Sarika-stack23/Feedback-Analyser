# 📊 Feedback Analyser

<div align="center">

![Feedback Analyser](https://img.shields.io/badge/Feedback%20Analyser-AI%20Powered-blue?style=for-the-badge&logo=python&logoColor=white)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-RoBERTa-FFD21E?style=flat-square&logo=huggingface&logoColor=black)](https://huggingface.co)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-44%20passing-brightgreen?style=flat-square&logo=pytest)](https://pytest.org)
[![Coverage](https://img.shields.io/badge/Coverage-82%25-green?style=flat-square)](https://pytest.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**AI-powered app review intelligence — collect, analyse, visualise, and act on user feedback automatically.**

[🚀 Live Demo](#-live-demo) • [⚙️ Quick Start](#-quick-start) • [📊 Dashboard](#-dashboard--10-tabs) • [🌐 Deploy](#-deploy-to-streamlit-cloud-free)

</div>

---

## 📋 Table of Contents

- [About](#-about)
- [Live Demo](#-live-demo)
- [Tech Stack](#-tech-stack)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Dashboard — 10 Tabs](#-dashboard--10-tabs)
- [REST API](#-rest-api)
- [Deploy to Streamlit Cloud](#-deploy-to-streamlit-cloud-free)
- [Database & Migrations](#-database--migrations)
- [Environment Variables](#-environment-variables)
- [Running Tests](#-running-tests)
- [Architecture](#-architecture)
- [Case Study Results](#-case-study-results)
- [Troubleshooting](#-troubleshooting)

---

## 🧠 About

**Feedback Analyser** is a complete, production-ready feedback intelligence system built in Python.

It aggregates reviews from **Google Play Store**, **Apple App Store**, **CSV surveys**, and **email feedback** — then uses AI to:

- Detect sentiment trends and spikes
- Prioritise critical bugs before they go viral
- Benchmark your app against competitors
- Segment your customer base
- Calculate the ROI of fixing each issue
- Generate professional PDF stakeholder reports

> Built as a **Day 20 Capstone Project** for the HiDevs AI Systems & Engineering track.

---

## 🚀 Live Demo

| Resource | URL |
|---|---|
| 🌐 **Streamlit Dashboard** | *(Deploy using steps below → free on Streamlit Cloud)* |
| 📖 **FastAPI Swagger Docs** | `http://localhost:8000/docs` (run locally) |
| 🎮 **Demo Mode** | Click **Load Demo Data** in sidebar — no API keys needed |

---

## 🛠 Tech Stack

| Category | Technology | Purpose |
|---|---|---|
| **Dashboard** | Streamlit 1.35+ | 10-tab interactive UI |
| **ML Model** | HuggingFace RoBERTa | Sentiment analysis (~92% accuracy) |
| **AI Insights** | Groq + Llama3 | Executive summaries + response suggestions |
| **REST API** | FastAPI + Uvicorn | OpenAPI/Swagger documented endpoints |
| **Database** | SQLAlchemy + SQLite | Zero-config local, PostgreSQL-ready |
| **Charts** | Plotly + Matplotlib | Interactive charts + word clouds |
| **PDF Reports** | FPDF2 | Professional downloadable reports |
| **Data Sources** | google-play-scraper + RSS | Live review fetching |
| **Keyword Extraction** | YAKE | Automatic keyword detection |
| **ML Forecasting** | scikit-learn | 14-day sentiment prediction |
| **Testing** | pytest + pytest-cov | 44 tests, 82% coverage |
| **CI/CD** | GitHub Actions | Auto test + Docker build on push |
| **Deployment** | Docker + Streamlit Cloud | One-command or free cloud deploy |

---

## ✨ Features

| Feature | Description |
|---|---|
| 📱 **Multi-source ingestion** | Google Play, App Store, CSV, Email (.eml / .txt) |
| 🧠 **AI Sentiment Analysis** | HuggingFace RoBERTa transformer — 92% accuracy |
| 📈 **Trend Detection** | Daily/weekly sentiment with spike alerts |
| 🚨 **Issue Prioritisation** | Critical / Moderate / Low scoring tiers |
| 🔮 **Predictive Analytics** | 14-day sentiment forecast via linear regression |
| 🏆 **Competitor Benchmarking** | Side-by-side rating + sentiment comparison |
| 👥 **Customer Segmentation** | Champions, Loyal, Neutral, At-Risk, Churned |
| 💰 **ROI Calculator** | Revenue impact of fixing each critical issue |
| 🌍 **Multi-language Detection** | English, Spanish, French, Hindi, Japanese + more |
| 🤖 **AI Insights (Groq)** | Llama3 executive summaries — free API |
| 💬 **Auto Response Suggestions** | AI-drafted replies to negative reviews |
| 📄 **PDF Reports** | Professional weekly reports with charts |
| 🔔 **Sentiment Alerts** | Critical/warning banners when sentiment drops |
| 🎮 **Demo Mode** | 150 pre-loaded sample reviews — no API needed |
| 🐳 **Docker Ready** | One-command deployment with Docker Compose |
| ⚙️ **CI/CD Pipeline** | GitHub Actions — test + lint + Docker build |
| 🗄️ **Database Migrations** | Versioned schema with rollback support |

---

## 📁 Project Structure

```
feedback-analyser/
│
├── main.py                  # Complete Streamlit dashboard (2,500+ lines)
├── api.py                   # FastAPI REST API with Swagger docs
├── database.py              # SQLAlchemy ORM models + CRUD helpers
├── migrations.py            # Database schema migration scripts
├── tests.py                 # pytest test suite (44 tests)
│
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # One-command deployment
├── requirements.txt         # All Python dependencies
├── sample_data.csv          # 50 sample reviews for testing
├── .env.example             # Environment variable template
│
├── README.md                # This file
├── CASE_STUDY.md            # Business impact case study
│
└── .github/
    └── workflows/
        └── ci.yml           # GitHub Actions CI/CD pipeline
```

---

## ⚡ Quick Start

### Option 1 — Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/Sarika-stack23/feedback-analyser.git
cd feedback-analyser

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run database migrations
python migrations.py

# 4. Start the dashboard
streamlit run main.py
```

Open: `http://localhost:8501`

> **No API keys needed** — click **🎮 Load Demo Data** in the sidebar to explore instantly.

---

### Option 2 — Docker (One Command)

```bash
docker-compose up --build
```

Open: `http://localhost:8501`

```bash
# Stop
docker-compose down
```

---

### Option 3 — REST API Only

```bash
uvicorn api:app --reload --port 8000
```

Open Swagger UI: `http://localhost:8000/docs`

---

## 📊 Dashboard — 10 Tabs

| # | Tab | What You Get |
|---|---|---|
| 1 | 📊 **Overview** | Key metrics, sentiment donut, rating chart, AI insights (Groq) |
| 2 | 📈 **Trends** | Sentiment over time, week-over-week, spike detection |
| 3 | 🔮 **Predictions** | 14-day forecast chart + projected rating |
| 4 | 🚨 **Issues** | Critical/Moderate/Low issues ranked, word cloud, AI response suggestions |
| 5 | 📋 **All Reviews** | Searchable, sortable, filterable table + CSV export |
| 6 | 🌍 **Languages** | Language distribution + sentiment breakdown per language |
| 7 | 🏆 **Benchmark** | Competitor comparison — rating distribution + radar chart |
| 8 | 👥 **Segments** | Customer segments donut + engagement strategy per segment |
| 9 | 💰 **ROI** | Revenue impact calculator — issue-by-issue ROI breakdown |
| 10 | 📄 **Reports** | Generate + download professional PDF weekly report |

---

## 🌐 Deploy to Streamlit Cloud (Free)

Streamlit Cloud hosts your app for **free** directly from GitHub. Here's how:

### Step 1 — Push your code to GitHub

```bash
git add .
git commit -m "Ready for Streamlit Cloud deployment"
git push origin main
```

### Step 2 — Go to Streamlit Cloud

Visit: [share.streamlit.io](https://share.streamlit.io)

Click **"Sign in with GitHub"** and authorise Streamlit.

### Step 3 — Create a New App

Click **"New app"** and fill in:

| Field | Value |
|---|---|
| **Repository** | `Sarika-stack23/feedback-analyser` |
| **Branch** | `main` |
| **Main file path** | `main.py` |
| **App URL** | Choose a custom name e.g. `feedback-analyser` |

### Step 4 — Add Secrets (Optional)

If you want Groq AI insights enabled on your live app:

1. In your app settings → click **"Secrets"**
2. Add:

```toml
GROQ_API_KEY = "gsk_your_key_here"
```

> Get a free Groq key at [console.groq.com](https://console.groq.com)

### Step 5 — Click Deploy! 🚀

Streamlit will:
- Install all packages from `requirements.txt`
- Run `main.py`
- Give you a public URL like:
  `https://feedback-analyser.streamlit.app`

### ⚠️ Important Notes for Streamlit Cloud

**1. Large ML model download**

The HuggingFace RoBERTa model (~500MB) downloads on first run. Streamlit Cloud caches it after the first deploy. First load may take 2-3 minutes.

**2. requirements.txt must be clean**

Make sure your `requirements.txt` doesn't have conflicting versions. The one in this repo is tested and working.

**3. No persistent storage**

Streamlit Cloud doesn't persist SQLite files between restarts. The app works fine because it uses in-memory/session state. For persistent storage, use a cloud database:

```toml
# In Streamlit secrets
DATABASE_URL = "postgresql://user:pass@host:5432/dbname"
```

**4. Demo Mode always works**

Even without any API keys or database, the **🎮 Load Demo Data** button works perfectly on Streamlit Cloud.

---

## 🌐 Alternative Free Deployment Options

### Railway (Recommended for persistent DB)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

Set environment variables in Railway dashboard.

### Render

1. Go to [render.com](https://render.com) → New Web Service
2. Connect your GitHub repo
3. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `streamlit run main.py --server.port $PORT --server.address 0.0.0.0`

### Hugging Face Spaces (Free)

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. New Space → Select **Streamlit**
3. Upload your files or connect GitHub
4. Add secrets in Space Settings

---

## 🔌 REST API

Base URL (local): `http://localhost:8000`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/reviews/fetch` | Fetch from app stores (background job) |
| POST | `/reviews/upload` | Upload CSV file |
| GET | `/reviews` | List all stored reviews |
| GET | `/reviews/{id}` | Get single review by ID |
| GET | `/analytics/summary` | Sentiment overview metrics |
| GET | `/analytics/trends` | WoW trends + spike detection |
| GET | `/analytics/issues` | Prioritised issues list |
| GET | `/analytics/daily` | Day-by-day sentiment data |
| GET | `/reports/pdf` | Download PDF report |
| GET | `/jobs/{job_id}` | Check background job status |

Full interactive docs: `http://localhost:8000/docs`

---

## 🗄 Database & Migrations

### Run Migrations

```bash
python migrations.py migrate      # Apply all pending migrations
python migrations.py status       # Check current state
python migrations.py rollback     # Rollback last 1 migration
python migrations.py rollback 2   # Rollback last 2 migrations
```

### Database Schema

```
reviews              — All fetched reviews with sentiment scores
analysis_jobs        — Background fetch job tracking
issues               — Detected + prioritised issues
reports              — Generated report history
customer_segments    — Segmentation results per review
competitor_reviews   — Competitor benchmark review data
roi_calculations     — ROI analysis results per issue
```

### Switch to PostgreSQL

```bash
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/feedback_analyser
```

Then uncomment `psycopg2-binary` in `requirements.txt`.

---

## 🔑 Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Free key from [console.groq.com](https://console.groq.com) |
| `DATABASE_URL` | SQLite (local) | PostgreSQL URL for production |
| `DEFAULT_PLAY_APP_ID` | `com.spotify.music` | Default Google Play app |
| `DEFAULT_APP_STORE_ID` | `324684580` | Default App Store app ID |
| `DEFAULT_COUNTRY` | `us` | Default country code |
| `STREAMLIT_SERVER_PORT` | `8501` | Dashboard port |

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests.py -v

# Run with coverage report
pytest tests.py -v --cov=main --cov-report=term-missing

# Run a specific test class
pytest tests.py::TestCleanText -v
pytest tests.py::TestEndToEndPipeline -v
```

Expected output:
```
=================== 44 passed in 7.17s ===================
Coverage: 82%
```

### Test Coverage

| Module | Tests | Coverage |
|---|---|---|
| `clean_text` | 7 tests | ✅ |
| `standardize_reviews` | 6 tests | ✅ |
| `rating_to_sentiment` | 7 tests | ✅ |
| `calculate_daily_sentiment` | 5 tests | ✅ |
| `week_over_week` | 4 tests | ✅ |
| `detect_spikes` | 3 tests | ✅ |
| `score_issues` | 4 tests | ✅ |
| `assign_priority` | 3 tests | ✅ |
| `sanitize_pdf_text` | 4 tests | ✅ |
| `end_to_end_pipeline` | 1 test | ✅ |

---

## 🏗 Architecture

```
[Data Sources]
  Google Play  ──┐
  App Store    ──┼──► Fetchers ──► Preprocessor ──► Sentiment Engine
  CSV / Email  ──┘                                        │
                                   ┌────────────────────┼────────────────────┐
                                   ▼                    ▼                    ▼
                             Trend Engine         Issue Scorer        Keyword Extractor
                                   └────────────────────┼────────────────────┘
                                                        ▼
                                            Streamlit Dashboard
                                ┌──────────────────────────────────────────┐
                                │  Overview │ Trends │ Predictions          │
                                │  Issues  │ Reviews │ Languages             │
                                │  Benchmark │ Segments │ ROI │ Reports     │
                                └──────────────────────────────────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────┐
                              ▼                         ▼                     ▼
                         PDF Reports               FastAPI               SQLAlchemy
                           FPDF2               Swagger UI            SQLite / PostgreSQL
```

---

## 📈 Case Study Results

Full details in [`CASE_STUDY.md`](CASE_STUDY.md)

| Metric | Before | After | Change |
|---|---|---|---|
| Time to detect critical bug | 11 days | 6 hours | **97% faster** |
| Manual review time/week | 8 hours | 45 minutes | **−91%** |
| Reviews processed/hour | ~50 (manual) | 1,200+ (automated) | **24x** |
| App Store rating | 3.8 ⭐ | 4.2 ⭐ | **+0.4 stars** |
| Negative review volume | baseline | −34% MoM | ✅ |
| **3-Month ROI** | $8,000 invested | $52,200 return | **653% ROI** |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| Model slow on first run | Downloads ~500MB once, cached after that |
| Google Play returns empty | Verify app ID, try `country=us` |
| App Store returns empty | Verify numeric app ID from URL |
| PDF fails to generate | Unicode chars are auto-sanitised — update to latest `main.py` |
| Port 8501 already in use | `streamlit run main.py --server.port 8502` |
| Docker build fails | Run `docker system prune` then rebuild |
| Groq API error | Check key at [console.groq.com](https://console.groq.com) — use `llama-3.1-8b-instant` |
| CSV not loading | Column must be named `text`, `review`, `comment`, or `feedback` |
| Streamlit Cloud timeout | First deploy takes 2-3 mins to download ML model |
| ModuleNotFoundError | Run `pip install -r requirements.txt` |

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

```bash
# Fork → Clone → Create branch
git checkout -b feature/your-feature

# Make changes → Test
pytest tests.py -v

# Commit → Push → PR
git commit -m "feat: your feature"
git push origin feature/your-feature
```

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">

Built with ❤️ by <a href="https://github.com/Sarika-stack23">Sarika</a>
<br/>
<sub>HiDevs AI Systems & Engineering — Day 20 Capstone Project | March 2026</sub>
<br/><br/>

[![Deploy to Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

</div>