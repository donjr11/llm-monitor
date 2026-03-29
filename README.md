<div align="center">

# 🔭 LLM Monitor
### EPINEON AI — LLM Monitoring System
**PFE Challenge 2026 · ESITH Cohort**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

> An automated pipeline for **collecting**, **normalizing**, **scoring**, and **recommending** LLMs by enterprise use-case — powered by **AHP + TOPSIS** multi-criteria decision analysis.

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Modules](#-modules)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [API Reference](#-api-reference)
- [Enterprise Profiles](#-enterprise-profiles)
- [Scoring Methodology](#-scoring-methodology)
- [Data Sources](#-data-sources)
- [Automation](#-automation-n8n)
- [Project Structure](#-project-structure)
- [Technical Decisions](#-technical-decisions)

---

## 🎯 Overview

LLM Monitor tracks **55+ large language models** across 3 live data sources, scores them using a mathematically rigorous **AHP+TOPSIS** algorithm, and delivers ranked recommendations tailored to 5 enterprise use-case profiles.

| Metric | Value |
|--------|-------|
| Models tracked | 55+ |
| Data sources | 3 (HuggingFace, OpenRouter/AA, LLM Stats) |
| Metrics per model | 8 (intelligence, price in/out, speed, TTFT, context, license) |
| Enterprise profiles | 5 |
| Scoring methods | AHP+TOPSIS & TOPSIS |
| Dashboards | 2 (Plotly Dash + Next.js) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA COLLECTION                              │
│                                                                     │
│  HuggingFace API      OpenRouter API       llm-stats.com           │
│  (24 OSS models)   (live pricing/context)  (supplemental)          │
│       │                    │                     │                  │
│       └────────────────────┴─────────────────────┘                  │
│                            │                                        │
│                     ┌──────▼──────┐                                 │
│                     │  Normalizer  │  min-max → norm_* columns      │
│                     └──────┬──────┘                                 │
└────────────────────────────┼────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                        SQLITE DATABASE                              │
│         LLMModel · ScoringRun · ModelSnapshot                      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────────┐
│                        SCORING ENGINE                               │
│                                                                     │
│   ┌──────────┐    ┌─────────────┐    ┌─────────────────────────┐   │
│   │   AHP    │───▶│   TOPSIS    │───▶│  Profile Recommender    │   │
│   │ Weights  │    │  Ranking    │    │  (5 enterprise profiles) │   │
│   └──────────┘    └─────────────┘    └─────────────────────────┘   │
└──────────┬──────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                             │
│                                                                     │
│   FastAPI REST API      Plotly Dash         Next.js Dashboard      │
│     (port 8000)         (port 8050)           (port 3000)           │
│                                                                     │
│   N8N Automation — daily 8AM: collect → score → email digest       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Modules

### Module 1 — Data Collection & Normalization

| Collector | Source | Models | Live Data |
|-----------|--------|--------|-----------|
| `huggingface.py` | HF Model API + HF Open LLM Leaderboard | 24 OSS models | Pricing via OpenRouter |
| `artificial_analysis.py` | OpenRouter API + AA benchmarks | 28 commercial models | Live pricing |
| `llmstats.py` | llm-stats.com (HTML scraping) | 14+ supplemental | With fallback |
| `normalizer.py` | All collected models | All | Min-max scaling |

**All collectors follow the same production pattern:**
- `requests.Session` with proper browser-like headers
- Exponential backoff retry (3 attempts, 2× backoff per attempt)
- Reference fallback data when the live source is unavailable
- Smart upsert — enriches existing records, never overwrites higher-quality data

**New model detection:** The `is_new` flag is set `True` only during live `/collect` runs for models not previously in the database. It is reset to `False` at every API startup (transient flag — avoids stale "new" badges).

---

### Module 2 — Scoring & Recommendation Engine

#### AHP (Analytic Hierarchy Process)
Pairwise comparison matrices (Saaty 1–9 scale) derive mathematically consistent weights per profile.

**All 5 profiles validated — Consistency Ratio CR < 0.10 ✅**

| Profile | CR |
|---------|----|
| Coding | 0.028 |
| Reasoning | 0.054 |
| RAG Long Context | 0.019 |
| Minimum Cost | 0.029 |
| Enterprise Agents | 0.054 |

#### TOPSIS (6-step algorithm)

```
Step 1  Load normalized metrics from DB
Step 2  Build weighted matrix  →  w_j × r_ij
Step 3  Ideal best (V+) and worst (V-) per criterion
Step 4  Euclidean distance  D+ and D-  for each model
Step 5  Score = D- / (D+ + D-)
Step 6  Rank descending — score closest to 1.0 wins
```

**REST endpoint:**
```
GET /recommend?profile=coding&commercial=true&method=ahp_topsis&top_n=5
```

---

### Module 3 — Visualization & Digest Reports

**Plotly Dash Dashboard** (`dashboard/app.py` — port 8050)
- Top 5 recommendation cards with TOPSIS score bars, D+/D− distances, justification text
- TOPSIS score ranking bar chart (top 15 models)
- Intelligence vs Cost scatter plot (bubble size = context window)
- Full model leaderboard — sortable, filterable, paginated
- **📄 Generate Markdown Report** button — on-demand digest export

**Next.js Dashboard** (`next-dashboard/` — port 3000)
- EPINEON AI dark navy theme (`#070d1a` background · `#22d3ee` cyan accent)
- Real-time data from FastAPI with skeleton loaders
- 4 KPI cards — Total Models, New Models, Profiles, Avg Intelligence
- Scoring method toggle: AHP+TOPSIS / TOPSIS only
- Commercial license filter
- Fully sortable models table with search

**Auto-generated Digest Reports** (`reports/`)
- Triggered via `GET /report/generate` or the dashboard button
- Detects significant movements: price ±10%, score ±2pts, speed +15%
- Top 5 models per profile with justifications
- Saved as `reports/digest_YYYYMMDD_HHMMSS.md`

---

## 🛠️ Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend API | FastAPI + Uvicorn | Async, auto OpenAPI docs, fast startup |
| Database | SQLite + SQLAlchemy ORM | Zero-config, portable, sufficient for this scale |
| Scoring | Custom AHP+TOPSIS (NumPy) | Mathematically sound MCDM, auditable weights |
| Dash UI | Plotly Dash + Bootstrap CYBORG | Python-native reactive UI, no JS required |
| Next.js UI | Next.js 16.2 + Tailwind v4 + shadcn/ui | Modern, type-safe, production-grade components |
| HTTP | requests + exponential backoff | Resilient external API calls |
| Scraping | BeautifulSoup4 | Lightweight, battle-tested HTML parsing |
| Templates | Jinja2 | Markdown report generation |
| Automation | N8N | Low-code, visual workflow, SMTP built-in |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### 1 — Clone & Setup

```bash
git clone https://github.com/donjr11/llm-monitor.git
cd llm-monitor

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / Mac

pip install -r requirements.txt
```

### 2 — Configure Environment

```bash
cp .env.example .env
# Add your HuggingFace API token (optional — improves data quality)
```

### 3 — Start the Backend

```bash
# Windows (required for emoji in console output)
set PYTHONIOENCODING=utf-8
venv\Scripts\python.exe -m uvicorn api.main:app --port 8000 --reload

# Linux / Mac
uvicorn api.main:app --port 8000 --reload
```

> On first launch the backend automatically seeds the database with 55+ models from all 3 sources. This takes ~30 seconds.

### 4 — Start a Dashboard

**Option A — Plotly Dash (Python, no extra install)**
```bash
venv\Scripts\python.exe dashboard/app.py
# Visit http://localhost:8050
```

**Option B — Next.js (recommended)**
```bash
cd next-dashboard
npm install
npm run dev
# Visit http://localhost:3000
```

### 5 — One-Command Launch (Windows only)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run-all.ps1
```

Opens three PowerShell windows (backend, dashboard, N8N) and browser tabs automatically.

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/models` | All models — filters: `source`, `provider`, `license` |
| `GET` | `/models/new` | Models flagged as new in the latest collection run |
| `GET` | `/profiles` | All enterprise profiles with AHP weights |
| `GET` | `/recommend` | Top-N recommendations for a profile |
| `GET` | `/recommend/all` | Score all 5 profiles in one request |
| `POST` | `/collect` | Trigger full collection + normalization pipeline |
| `GET` | `/report/generate` | Generate and save markdown digest report |

**Interactive docs:** `http://localhost:8000/docs`

### Example — Top 3 Coding Models (commercial only)

```bash
curl "http://localhost:8000/recommend?profile=coding&commercial=true&method=ahp_topsis&top_n=3"
```

```json
{
  "profile": "coding",
  "method": "ahp_topsis",
  "consistency_ratio": 0.028,
  "results": [
    {
      "rank": 1,
      "name": "Gemini-2.5-Pro",
      "provider": "google",
      "score": 0.8921,
      "justification": "Achieves the highest TOPSIS score driven by the top intelligence score (91.2/100) and competitive pricing relative to its quality tier.",
      "metrics": {
        "intelligence": 91.2,
        "price_input": 1.25,
        "speed_tps": 72,
        "ttft_ms": 380,
        "context_window": 1000000,
        "license": "proprietary"
      }
    }
  ]
}
```

---

## 👔 Enterprise Profiles

| Profile | Key Weights | Best For |
|---------|-------------|----------|
| **💻 Coding / Dev** | Intelligence 35% · Speed 25% · Price 20% | Code generation, debugging, review |
| **🧠 Reasoning / Analysis** | Intelligence 50% · TTFT 20% · Price 15% | Legal analysis, financial modeling, research |
| **📄 RAG Long Context** | Context 40% · Intelligence 25% · Price 20% | Document Q&A, large-corpus RAG pipelines |
| **💰 Minimum Cost** | Price 55% · Speed 20% · Intelligence 15% | High-volume classification, moderation at scale |
| **🤖 Enterprise Agents** | Intelligence 40% · TTFT 25% · Speed 20% | Autonomous agents, multi-step tool use |

**Compliance filter:** when `commercial=true`, models with non-commercial licenses (GPL, CC-BY-NC, Llama community license, etc.) are automatically excluded.

---

## 📐 Scoring Methodology

### Why AHP + TOPSIS?

Standard weighted averages suffer from rank reversal and cannot validate that weights are logically consistent. AHP+TOPSIS addresses both issues:

**AHP** derives criterion weights from pairwise comparisons on the Saaty 1–9 scale. The Consistency Ratio (CR < 0.10) confirms that judgments are logically coherent — if you say A is twice as important as B and B is twice as important as C, you cannot also say C is more important than A.

**TOPSIS** ranks alternatives by their geometric distance to the ideal best (V+) and worst (V−) solutions simultaneously. A model that is good overall but never catastrophically bad outranks a model that dominates one criterion and fails the others.

### Criteria & Normalization

| Criterion | Direction | Source |
|-----------|-----------|--------|
| Intelligence Score (0–100) | ↑ Higher is better | AA Quality Index (MMLU/GPQA/MATH composite) |
| Price ($/1M tokens avg) | ↓ Lower is better | OpenRouter live pricing |
| Speed (output tokens/s) | ↑ Higher is better | AA Performance benchmarks |
| TTFT — Time to First Token (ms) | ↓ Lower is better | AA Performance benchmarks |
| Context Window (tokens) | ↑ Higher is better | OpenRouter / HuggingFace API |

All criteria normalized to [0, 1] using min-max scaling before TOPSIS weighted matrix construction.

---

## 📊 Data Sources

### HuggingFace
- **API:** `https://huggingface.co/api/models`
- **Data:** License type, context window, evaluation scores
- **Models:** 24 open-source models — Llama 3.x, Mistral, Gemma, Qwen, Phi, DeepSeek, Falcon, Yi, Zephyr
- **Pricing:** Enriched via OpenRouter API in real time

### Artificial Analysis (via OpenRouter)
- **Live pricing:** `https://openrouter.ai/api/v1/models` — free public API, no authentication
- **Quality/Performance:** Reference benchmarks from artificialanalysis.ai (March 2026)
- **Models:** 28 commercial APIs — GPT-4o series, Claude 3.x, Gemini 1.5/2.0/2.5, Grok, Mistral, DeepSeek, Qwen
- **Design decision:** Pricing and context are fetched live (change daily); benchmark scores are stable reference data (change only on major model releases)

### LLM Stats
- **URL:** `https://llm-stats.com`
- **Data:** Supplemental models not covered by the above sources
- **Strategy:** Inserts new models only; enriches existing records where data is missing — never overwrites higher-quality data from the primary collectors

---

## ⚡ Automation (N8N)

The bonus module automates the full pipeline on a daily schedule.

```
[Daily 08:00 AM]
       │
       ▼
[POST /collect]          ← Trigger data collection from all 3 sources
       │
       ▼
[GET /models/new]        ← Detect newly added models
       │
       ▼
[GET /recommend/all]     ← Score all 5 enterprise profiles
       │
       ▼
[GET /report/generate]   ← Generate markdown digest file
       │
       ▼
[Build HTML Email]       ← KPIs + new models + top-3 per profile
       │
       ▼
[Send via SMTP]          ← Delivered to configured recipient
```

**Setup in 4 steps:**
1. Start N8N: `docker run -d --name n8n -p 5678:5678 --network host n8nio/n8n`
2. Import `n8n-workflow.json` via Settings → Import
3. Add SMTP credentials and set recipient address
4. Click **Execute Workflow** to test, then toggle **Active**

Full guide: [N8N-SETUP.md](N8N-SETUP.md)

---

## 📁 Project Structure

```
llm-monitor/
│
├── api/
│   └── main.py                  # FastAPI — 8 endpoints, auto-init, CORS
│
├── collectors/
│   ├── artificial_analysis.py   # OpenRouter API + AA quality/perf benchmarks
│   ├── huggingface.py           # HF Model API + Open LLM Leaderboard
│   ├── llmstats.py              # llm-stats.com scraper with fallback
│   └── normalizer.py            # Min-max normalization for all 5 criteria
│
├── scoring/
│   ├── ahp.py                   # Pairwise matrices + CR consistency validation
│   ├── engine.py                # TOPSIS 6-step ranking algorithm
│   └── profiles.py              # 5 enterprise profiles with criterion weights
│
├── dashboard/
│   └── app.py                   # Plotly Dash dark dashboard (port 8050)
│
├── next-dashboard/              # Next.js 16.2 dashboard (port 3000)
│   └── src/app/
│       ├── page.tsx             # Full dashboard — KPIs, profiles, leaderboard
│       ├── layout.tsx           # Inter font, dark mode, EPINEON meta
│       └── globals.css          # EPINEON dark navy theme (oklch color space)
│
├── reports/
│   ├── generator.py             # Digest report + snapshot + movement detection
│   └── template.md              # Jinja2 markdown template
│
├── data/
│   └── llm_monitor.db           # SQLite database (auto-created on first run)
│
├── database.py                  # SQLAlchemy models — LLMModel, ScoringRun, ModelSnapshot
├── config.py                    # DB path, API tokens from environment
├── n8n-workflow.json            # N8N 7-node automation workflow
├── run-all.ps1                  # PowerShell one-command project launcher
├── N8N-SETUP.md                 # Step-by-step N8N configuration guide
├── requirements.txt             # Python dependencies (pinned versions)
├── Dockerfile                   # HuggingFace Spaces deployment (port 7860)
└── Procfile                     # Heroku deployment ($PORT dynamic binding)
```

---

## 🎓 Technical Decisions

| Decision | Choice | Justification |
|----------|--------|---------------|
| **Database** | SQLite | Zero-config, portable, no external service needed for 55 models |
| **Scoring** | AHP+TOPSIS | Mathematically rigorous MCDM; CR validates logical consistency; TOPSIS avoids rank reversal |
| **API** | FastAPI | Async, auto-generates OpenAPI docs at `/docs`, Pydantic validation |
| **Pricing source** | OpenRouter | Free public API, no auth required, covers 300+ models in real-time |
| **Benchmarks** | Artificial Analysis reference | Most comprehensive quality index (MMLU+GPQA+MATH+HumanEval); JS-rendered site → stable reference data is more reliable than scraping |
| **Automation** | N8N | Visual workflow editor, SMTP built-in, easy to demonstrate and hand over to a non-developer team |
| **Front-end** | Next.js 16.2 + Tailwind v4 | Type-safe, production-grade, dark theme aligned with EPINEON brand |

---

<div align="center">

Built for **EPINEON AI** · PFE 2026 · ESITH Cohort

*Submitted to recrutement@epineon.ai*

</div>
