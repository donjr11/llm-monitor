# N8N Workflow Setup Guide
**EPINEON AI — LLM Monitor — Daily Digest Automation**

---

## Overview

The N8N workflow automates the full LLM monitoring pipeline:

```
Every day at 8:00 AM
        │
        ▼
POST /collect          ← Runs HuggingFace + Artificial Analysis + LLM Stats collectors
        │
        ▼
GET /models/new        ← Fetches newly detected models
        │
        ▼
GET /recommend/all     ← Gets top-3 recommendations for all 5 enterprise profiles
        │
        ▼
GET /report/generate   ← Saves markdown digest to reports/
        │
        ▼
Build Digest Email     ← Formats HTML email with scores, new models, status
        │
        ▼
Send Email             ← Delivers to your inbox via SMTP
```

---

## Prerequisites

| Requirement | Check |
|---|---|
| FastAPI backend running | `http://localhost:8000` returns `{"status":"ok"}` |
| n8n running | `http://localhost:5678` loads the n8n UI |
| SMTP account | Gmail, Outlook, or any mail server |

> Run `run-all.ps1` to start all services at once.

---

## Step-by-Step Setup

### Step 1 — Open n8n

Navigate to **http://localhost:5678** in your browser.

On first launch, create a local account (email + password — stored locally only).

---

### Step 2 — Import the Workflow

1. In the n8n sidebar, click **Workflows**
2. Click **Add Workflow** → **Import from File**
3. Select `n8n-workflow.json` from the project root
4. The workflow opens with 7 nodes arranged in a pipeline

You should see:

```
[Daily at 8 AM] → [Run Collection] → [Get New Models]
  → [Get All Recommendations] → [Generate Report]
  → [Build Digest Email] → [Send Email]
```

---

### Step 3 — Configure SMTP Credentials

The **Send Email** node requires SMTP credentials.

1. Click the **Send Email** node
2. Click the **Credential** dropdown → **Create New**
3. Select **SMTP**
4. Fill in your mail server details:

**Gmail example:**
```
Host:       smtp.gmail.com
Port:       465
User:       your-gmail@gmail.com
Password:   your-app-password   ← Generate at myaccount.google.com/apppasswords
SSL/TLS:    SSL
```

**Outlook/Hotmail example:**
```
Host:       smtp-mail.outlook.com
Port:       587
User:       your-email@outlook.com
Password:   your-password
SSL/TLS:    STARTTLS
```

5. Click **Save** then **Test Connection** to verify

---

### Step 4 — Set the Recipient Email

1. In the **Send Email** node, change:
   ```
   To Email: your-email@example.com
   ```
   to your actual email address

2. Optionally change `From Email` to match your SMTP user

---

### Step 5 — Test the Workflow

Before activating the daily schedule, run it manually:

1. Click **Execute Workflow** (▶ button, top right)
2. Watch each node turn green as it executes
3. Check your inbox — you should receive the digest email within 1-2 minutes

> **Note:** The first execution triggers data collection which can take 3-5 minutes.
> The `Run Collection` node has a 5-minute timeout configured.

**If a node fails:**
- Click the red node to see the error
- `Run Collection` errors usually mean the backend is not running → start it first
- `Send Email` errors are usually credential issues → re-check SMTP settings

---

### Step 6 — Activate the Workflow

Once the test succeeds:

1. Toggle the **Active** switch (top-right of the workflow editor)
2. The workflow is now scheduled — it will run automatically every day at **8:00 AM**

---

## Workflow Details

### Schedule
The trigger uses a cron expression: `0 8 * * *` (08:00 local time, every day).

To change the time, click **Daily at 8 AM** and edit the expression:
```
0 8 * * *     → every day at 8:00 AM
0 6 * * 1-5   → weekdays at 6:00 AM
0 */4 * * *   → every 4 hours
```

### Email Content

Each digest email contains:

| Section | Description |
|---|---|
| **KPI row** | Total models tracked / new models / profiles scored |
| **Collection Status** | OK or error per source (HuggingFace, Artificial Analysis, LLM Stats) |
| **New Models** | List of models seen for the first time (if any) |
| **Recommendations** | Top 3 models per profile (Coding, Reasoning, RAG, Cost, Agents) with AHP+TOPSIS scores |

### API Endpoints Used

| Node | Method | Endpoint |
|---|---|---|
| Run Collection | `POST` | `http://localhost:8000/collect` |
| Get New Models | `GET` | `http://localhost:8000/models/new` |
| Get All Recommendations | `GET` | `http://localhost:8000/recommend/all` |
| Generate Report | `GET` | `http://localhost:8000/report/generate` |

---

## Troubleshooting

### n8n can't reach `localhost:8000`

If n8n is running inside Docker, `localhost` resolves to the container, not the host.

**Solution A — Use npx (recommended for dev):**
```powershell
npx n8n
```
This runs n8n on the host where `localhost:8000` works directly.

**Solution B — Docker with host networking (Linux only):**
```bash
docker run -d --name n8n --network host n8nio/n8n
```

**Solution C — Docker on Windows/Mac, use `host.docker.internal`:**
Replace `localhost` with `host.docker.internal` in all HTTP Request nodes:
```
http://host.docker.internal:8000/collect
```

---

### Workflow not sending email

1. Check SMTP credentials (Step 3)
2. For Gmail: make sure you're using an **App Password** (not your normal password)
3. Check your spam folder

### Collection takes too long / times out

The `Run Collection` node has a 5-minute timeout. If your internet is slow:
1. Click the **Run Collection** node
2. Under **Options** → **Timeout**, increase to `600000` (10 minutes)

---

## File Locations

| File | Description |
|---|---|
| `n8n-workflow.json` | N8N workflow — import this into n8n |
| `run-all.ps1` | Launches backend + dashboard + n8n |
| `reports/digest_*.md` | Auto-generated markdown reports |
| `data/llm_monitor.db` | SQLite database |

---

*EPINEON AI · LLM Monitor · PFE Challenge 2026 — ESITH*
