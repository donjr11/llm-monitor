---
title: LLM Monitor API
emoji: 🔭
colorFrom: indigo
colorTo: green
sdk: docker
pinned: false
---

# LLM Monitoring System API

Automated pipeline for collecting, scoring, and recommending LLMs by enterprise profile.

## Scoring Method
AHP + TOPSIS (Multi-Criteria Decision Analysis)

## Data Sources
- HuggingFace API
- Artificial Analysis
- LLM Stats

## API Endpoints
- `GET /` — health check
- `GET /models` — list all models
- `GET /recommend?profile=coding&method=ahp_topsis` — get recommendations
- `GET /profiles` — list enterprise profiles
- `GET /report/generate` — generate digest report

---
title: LLM Monitor API
emoji: 🔭
colorFrom: indigo
colorTo: green
sdk: docker
pinned: false
---

# 🔭 LLM Monitoring System

> Epineon AI — Technical Challenge PFE 2026 | ESITH Cohort

Automated pipeline for **collecting**, **scoring**, and **recommending** Large Language Models by enterprise profile using **AHP+TOPSIS** (Multi-Criteria Decision Analysis).

---

## 🏗️ Architecture
```
HuggingFace API ──────┐
HF Open LLM Leaderboard┤
OpenRouter API ────────┤
                       ├──► Normalizer ──► SQLite DB ──► AHP+TOPSIS Engine ──► FastAPI ──► Dash Dashboard
Artificial Analysis ───┤                                        │
LLM Stats Scraper ─────┘                                 Digest Report (MD)
```

## 📦 Modules

### Module 1 — Data Collection
- **HuggingFace API** — live metadata (license, context window) + Open LLM Leaderboard scores for 24 open-source models
- **OpenRouter API** — live pricing data ($/M tokens input & output) fetched from openrouter.ai/api/v1/models
- **Artificial Analysis** — live scraping of artificialanalysis.ai with documented fallback (12 proprietary/API models)
- **LLM Stats scraper** — BeautifulSoup scraping of llm-stats.com (19 models)
- **Total: 55 models, 8+ metrics each**
- Min-max normalization to 0-1 scale
- New model detection across collection runs
- All data sourced from verified public APIs; no fabricated values

### Module 2 — Scoring & Recommendation
- **AHP (Analytic Hierarchy Process)** — derives weights from pairwise comparison matrices (Saaty scale 1–9)
- **TOPSIS** — ranks models by Euclidean distance from ideal best/worst
- **5 enterprise profiles:** Coding, Reasoning, RAG Long Context, Minimum Cost, Enterprise Agents
- **Compliance filter:** excludes non-commercial licenses when `commercial=true`
- Consistency Ratio (CR) validation — all profiles CR < 0.10

### Module 3 — Visualization & Reporting
- **Plotly Dash dashboard** — interactive, filterable, profile-aware
- **Auto-generated digest report** — Markdown via Jinja2 template
- Score comparison bar chart with gold/silver/bronze ranking

---

## 🚀 Setup & Usage

### Prerequisites
- Python 3.11+
- Git

### Installation
```bash
git clone https://github.com/donjr11/llm-monitor.git
cd llm-monitor
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Configuration
```bash
cp .env.example .env
# Add your HuggingFace token to .env
```

### Run
```bash
# Terminal 1 — API
python -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — Dashboard
python dashboard/app.py
```

Open `http://127.0.0.1:8050` for the dashboard.

---

## 🌐 Live API

**Base URL:** `https://donjr11-llm-monitor-api.hf.space`

| Endpoint | Description |
|---|---|
| `GET /` | Health check |
| `GET /models` | List all 55 models |
| `GET /models/new` | Newly detected models |
| `GET /profiles` | Enterprise profiles with AHP weights |
| `GET /recommend?profile=coding&method=ahp_topsis` | Top 3 recommendations |
| `GET /recommend?profile=coding&method=topsis` | TOPSIS-only recommendations |
| `POST /collect` | Trigger collection pipeline |
| `GET /report/generate` | Generate digest report |

---

## 📊 Scoring Method — AHP + TOPSIS

**Why AHP+TOPSIS?**

Standard weighted scoring (WLAM) assigns arbitrary weights. AHP derives weights mathematically from pairwise comparisons using the Saaty scale, producing a Consistency Ratio (CR) that validates judgment quality. TOPSIS then ranks models by their geometric distance from the ideal best and worst solutions — capturing trade-offs that simple weighted sums miss.

| Profile | Top Weight | CR |
|---|---|---|
| Coding | Intelligence (0.497) | 0.028 ✅ |
| Reasoning | Intelligence (0.503) | 0.054 ✅ |
| RAG Long Context | Context Window (0.497) | 0.019 ✅ |
| Minimum Cost | Price (0.464) | 0.029 ✅ |
| Enterprise Agents | TTFT Latency (0.503) | 0.054 ✅ |

All CR values < 0.10 — judgments are mathematically consistent.

---

## 📁 Project Structure
```
llm-monitor/
├── collectors/
│   ├── huggingface.py       # HuggingFace API collector
│   ├── artificial_analysis.py # AA live scraper + reference fallback
│   ├── llmstats.py          # LLM Stats scraper
│   └── normalizer.py        # Min-max normalization
├── scoring/
│   ├── ahp.py               # AHP weight derivation
│   ├── engine.py            # TOPSIS scoring engine
│   └── profiles.py          # Enterprise profiles
├── api/
│   └── main.py              # FastAPI REST API
├── dashboard/
│   └── app.py               # Plotly Dash dashboard
├── reports/
│   ├── generator.py         # Digest report generator
│   └── template.md          # Jinja2 report template
├── database.py              # SQLAlchemy schema
├── config.py                # Configuration
├── Dockerfile               # HuggingFace Spaces deployment
└── requirements.txt
```

---

## ⚠️ Limitations & Future Improvements

- HuggingFace API unreachable from some networks (DNS restriction) — falls back to documented reference data
- LLM Stats scraping dependent on site structure — may need updates if site changes
- Artificial Analysis scraping depends on Next.js page structure — documented reference data used as fallback
- SQLite not suitable for production — PostgreSQL recommended for multi-user deployment
- Dashboard not yet deployed (runs locally) — Streamlit Cloud or HF Spaces planned

---

## 📄 Data Sources

| Source | Method | Data Provided | Models | Update |
|---|---|---|---|---|
| [HuggingFace Model API](https://huggingface.co/docs/hub/api) | Live REST API | License, context window, eval scores | 24 | Real-time |
| [HF Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) | Datasets API | Benchmark scores (MMLU, ARC, etc.) | 24 | Continuous |
| [OpenRouter API](https://openrouter.ai/api/v1/models) | Live REST API (no auth) | Pricing (input/output $/M tokens) | 24 | Real-time |
| [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models) | Live scraping + reference fallback | All metrics (quality, speed, pricing, latency) | 12 | On demand |
| [LLM Stats](https://llm-stats.com) | BeautifulSoup scraping | Context window, pricing | 19 | On demand |

### Fallback strategy
When a live API is unreachable, collectors use **documented reference data** with explicit source citations (URL + access date). Reference values are sourced from the same public platforms and can be independently verified. The collection log reports how many values came from live APIs vs reference data.

---

*Built by [donjr11](https://github.com/donjr11) — Epineon AI PFE Challenge 2026*