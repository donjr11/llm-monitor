# collectors/llmstats.py
#
# Collects supplemental LLM data from llm-stats.com.
#
# ── Data sources ─────────────────────────────────────────────────────────────
#
#  PRIMARY  — llm-stats.com (live HTML scraping)
#    URL  : https://llm-stats.com
#    Data : model names, context windows, pricing ($/1M tokens)
#    Auth : none required
#
#  REFERENCE — llm-stats.com documented entries (March 2026)
#    Data : Supplemental models not covered by the HuggingFace or
#           Artificial Analysis collectors.
#    Note : HTML table; structure may change without notice.
#           Reference values serve as a stable fallback.
#
# ── Design decisions ─────────────────────────────────────────────────────────
#
#  This collector acts as a SUPPLEMENT to the other two collectors:
#    - New models unknown to HuggingFace/AA are inserted.
#    - Existing models are enriched only if they lack context or price data.
#  This avoids overwriting higher-quality data from the primary collectors.
#
# ─────────────────────────────────────────────────────────────────────────────

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from database import get_session, LLMModel

logger = logging.getLogger(__name__)

# ── HTTP configuration ────────────────────────────────────────────────────────

LLMSTATS_URL       = "https://llm-stats.com"
REQUEST_TIMEOUT    = 20    # seconds; site can respond slowly
MAX_RETRIES        = 3
RETRY_BACKOFF_BASE = 2.0   # seconds, doubled on each retry

_SESSION_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Provider normalisation map ────────────────────────────────────────────────
# Maps lowercase keywords found in model names to canonical provider slugs.

_PROVIDER_MAP: dict[str, str] = {
    "gpt":         "openai",
    "o1":          "openai",
    "o3":          "openai",
    "openai":      "openai",
    "claude":      "anthropic",
    "anthropic":   "anthropic",
    "gemini":      "google",
    "gemma":       "google",
    "google":      "google",
    "grok":        "xai",
    "xai":         "xai",
    "mistral":     "mistralai",
    "mixtral":     "mistralai",
    "llama":       "meta-llama",
    "meta":        "meta-llama",
    "phi":         "microsoft",
    "microsoft":   "microsoft",
    "qwen":        "qwen",
    "command":     "cohere",
    "cohere":      "cohere",
    "deepseek":    "deepseek",
    "falcon":      "tii",
    "tii":         "tii",
    "yi":          "01-ai",
    "01-ai":       "01-ai",
    "jamba":       "ai21",
    "ai21":        "ai21",
    "dbrx":        "databricks",
    "databricks":  "databricks",
    "solar":       "upstage",
    "upstage":     "upstage",
    "sonar":       "perplexity",
    "perplexity":  "perplexity",
    "amazon":      "amazon",
    "titan":       "amazon",
    "nvidia":      "nvidia",
    "nemotron":    "nvidia",
    "nous":        "nousresearch",
    "hermes":      "nousresearch",
    "wizard":      "wizardlm",
    "zephyr":      "huggingfaceh4",
    "openchat":    "openchat",
    "stablelm":    "stabilityai",
    "stable":      "stabilityai",
}

# ── Reference data — llm-stats.com, March 2026 ───────────────────────────────
# Models typically tracked by llm-stats.com that are not covered by the
# HuggingFace or Artificial Analysis collectors.
#
# Only context_window is required for insertion; price fields are optional.
# license_type defaults to "unknown" when not publicly documented.

_REFERENCE_MODELS: list[dict] = [
    # Amazon Bedrock
    {"name": "Amazon Titan Text Lite",    "provider": "amazon",       "context_window": 4_096,   "price_input": 0.30,  "price_output": 0.40,  "license_type": "proprietary"},
    {"name": "Amazon Titan Text Express", "provider": "amazon",       "context_window": 8_192,   "price_input": 0.80,  "price_output": 1.60,  "license_type": "proprietary"},
    # AI21 Jamba
    {"name": "Jamba 1.5 Mini",            "provider": "ai21",         "context_window": 256_000, "price_input": 0.20,  "price_output": 0.40,  "license_type": "proprietary"},
    {"name": "Jamba 1.5 Large",           "provider": "ai21",         "context_window": 256_000, "price_input": 2.00,  "price_output": 8.00,  "license_type": "proprietary"},
    # NVIDIA
    {"name": "Nemotron 4 340B Instruct",  "provider": "nvidia",       "context_window": 4_096,   "price_input": 4.20,  "price_output": 4.20,  "license_type": "proprietary"},
    # Perplexity Sonar
    {"name": "Sonar Large",               "provider": "perplexity",   "context_window": 127_072, "price_input": 1.00,  "price_output": 1.00,  "license_type": "proprietary"},
    {"name": "Sonar Small",               "provider": "perplexity",   "context_window": 127_072, "price_input": 0.20,  "price_output": 0.20,  "license_type": "proprietary"},
    # Upstage Solar
    {"name": "Solar Pro",                 "provider": "upstage",      "context_window": 4_096,   "price_input": 0.97,  "price_output": 2.91,  "license_type": "proprietary"},
    # WizardLM
    {"name": "WizardLM-2 8x22B",          "provider": "wizardlm",     "context_window": 65_536,  "price_input": 0.65,  "price_output": 0.65,  "license_type": "apache"},
    # Nous Research
    {"name": "Nous Hermes 3 70B",         "provider": "nousresearch", "context_window": 131_072, "price_input": 0.35,  "price_output": 0.40,  "license_type": "llama-community"},
    # 01-AI
    {"name": "Yi Large",                  "provider": "01-ai",        "context_window": 32_768,  "price_input": 3.00,  "price_output": 3.00,  "license_type": "proprietary"},
    # Databricks
    {"name": "DBRX Instruct",             "provider": "databricks",   "context_window": 32_768,  "price_input": 0.75,  "price_output": 2.25,  "license_type": "apache"},
    # Stability AI
    {"name": "StableLM Zephyr 3B",        "provider": "stabilityai",  "context_window": 4_096,   "price_input": 0.10,  "price_output": 0.10,  "license_type": "apache"},
    # OpenChat
    {"name": "OpenChat 3.5 7B",           "provider": "openchat",     "context_window": 8_192,   "price_input": 0.07,  "price_output": 0.07,  "license_type": "apache"},
]

for _m in _REFERENCE_MODELS:
    _m["source"] = "llm_stats"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _build_session() -> requests.Session:
    """Return a requests.Session with standard browser-like headers."""
    s = requests.Session()
    s.headers.update(_SESSION_HEADERS)
    return s


def _get_with_retry(session: requests.Session, url: str) -> requests.Response | None:
    """
    GET a URL with exponential-backoff retry on transient failures.
    Returns the Response on success, None after all retries exhausted.
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            # 4xx errors are client-side — retrying won't help
            if status and 400 <= int(status) < 500:
                logger.error("Client error %s from %s — not retrying", status, url)
                return None
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "HTTP %s from %s — retry %d/%d in %.1fs",
                status, url, attempt + 1, MAX_RETRIES, wait,
            )
            time.sleep(wait)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "Network error: %s — retry %d/%d in %.1fs",
                exc, attempt + 1, MAX_RETRIES, wait,
            )
            time.sleep(wait)

    logger.error("All %d retries exhausted for %s", MAX_RETRIES, url)
    return None


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_price(value: str) -> float | None:
    """
    Extract a $/1M-token float from strings like '$0.50', '1.23', '0.075'.
    Returns None if the value is empty, non-numeric, or zero.
    """
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value.strip())
    try:
        f = float(cleaned)
        return f if f > 0 else None
    except ValueError:
        return None


def _parse_context(value: str) -> int | None:
    """
    Parse context window strings: '128K', '1M', '1,000,000', '32768'.
    Returns None if the value cannot be parsed.
    """
    if not value:
        return None
    v = value.strip().upper().replace(",", "")
    try:
        if "M" in v:
            return int(float(v.replace("M", "")) * 1_000_000)
        if "K" in v:
            return int(float(v.replace("K", "")) * 1_000)
        return int(float(v))
    except ValueError:
        return None


def _clean_name(name: str) -> str:
    """Collapse internal whitespace and strip the model name."""
    return re.sub(r"\s+", " ", name.strip())


def _guess_provider(name: str) -> str:
    """
    Infer provider from model name using _PROVIDER_MAP keyword matching.
    Returns 'unknown' when no keyword matches.
    """
    name_lower = name.lower()
    for keyword, provider in _PROVIDER_MAP.items():
        if keyword in name_lower:
            return provider
    return "unknown"


# ── HTML scraping ─────────────────────────────────────────────────────────────

def _scrape_live(session: requests.Session) -> list[dict] | None:
    """
    Scrape llm-stats.com and return a list of raw model dicts.

    Returns:
        list[dict]  — parsed rows on success (may be empty if page structure changed)
        None        — on network/HTTP failure (triggers fallback)
    """
    logger.info("Fetching %s ...", LLMSTATS_URL)
    resp = _get_with_retry(session, LLMSTATS_URL)
    if resp is None:
        return None

    soup  = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        logger.warning(
            "No <table> found on llm-stats.com — site structure may have changed"
        )
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # ── Extract column headers from the first row ──
    header_cells = rows[0].find_all(["th", "td"])
    col_names    = [c.get_text(strip=True).lower() for c in header_cells]
    logger.info("llm-stats.com columns detected: %s", col_names)

    models: list[dict] = []

    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        row_data = [c.get_text(strip=True) for c in cells]
        row_dict = {
            col: row_data[i]
            for i, col in enumerate(col_names)
            if i < len(row_data)
        }

        # ── Model name: try common column names, fallback to first cell ──
        name = (
            row_dict.get("model")      or
            row_dict.get("name")       or
            row_dict.get("model name") or
            row_data[0]
        ).strip()

        if not name or len(name) < 2:
            continue

        # ── Context window ──
        ctx_raw = (
            row_dict.get("context") or
            row_dict.get("context window") or
            row_dict.get("ctx len") or
            row_dict.get("ctx") or
            ""
        )

        # ── Pricing — prefer separate input/output columns ──
        price_in_raw = (
            row_dict.get("input price") or
            row_dict.get("price input") or
            row_dict.get("input ($/1m)") or
            row_dict.get("input") or
            row_dict.get("price") or
            row_dict.get("cost") or
            ""
        )
        price_out_raw = (
            row_dict.get("output price") or
            row_dict.get("price output") or
            row_dict.get("output ($/1m)") or
            row_dict.get("output") or
            price_in_raw   # symmetric fallback when only one price column exists
        )

        models.append({
            "name":           _clean_name(name),
            "provider":       _guess_provider(name),
            "context_window": _parse_context(ctx_raw),
            "price_input":    _parse_price(price_in_raw),
            "price_output":   _parse_price(price_out_raw),
            "source":         "llm_stats",
        })

    logger.info("Scraped %d model rows from llm-stats.com", len(models))
    return models


# ── Upsert logic ──────────────────────────────────────────────────────────────

def _upsert_models(model_list: list[dict]) -> tuple[int, int]:
    """
    Upsert model_list into the database:
      - New models (not in DB) are inserted if they have at least a context_window.
      - Existing models are enriched only when they lack context or price data.
        Higher-quality data from HuggingFace/AA is never overwritten.

    Returns:
        (saved_count, enriched_count)
    """
    session  = get_session()
    existing = {m.name: m for m in session.query(LLMModel).all()}

    saved    = 0
    enriched = 0

    for data in model_list:
        name = data.get("name", "").strip()
        if not name:
            continue

        if name in existing:
            record  = existing[name]
            changed = False

            # Only fill in gaps — never overwrite data from better sources
            if data.get("context_window") and not record.context_window:
                record.context_window = data["context_window"]
                changed = True
            if data.get("price_input") and not record.price_input:
                record.price_input  = data["price_input"]
                record.price_output = data.get("price_output") or data["price_input"]
                changed = True

            if changed:
                record.collected_at = datetime.now(timezone.utc)
                enriched += 1

        else:
            # Require at least a context_window to be worth inserting
            if not data.get("context_window"):
                continue

            session.add(LLMModel(
                name           = name,
                provider       = data.get("provider", "unknown"),
                context_window = data["context_window"],
                price_input    = data.get("price_input"),
                price_output   = data.get("price_output"),
                license_type   = data.get("license_type", "unknown"),
                source         = "llm_stats",
                is_new         = True,
                collected_at   = datetime.now(timezone.utc),
            ))
            # Track locally to prevent duplicate inserts within the same batch
            existing[name] = object()  # type: ignore[assignment]
            saved += 1

    session.commit()
    session.close()
    return saved, enriched


# ── Public entry point ────────────────────────────────────────────────────────

def collect() -> None:
    """
    Main collection entry point called by the pipeline.

    Strategy:
      1. Attempt to scrape live data from llm-stats.com.
      2. Upsert results: insert new models, enrich existing ones.
      3. Fall back to documented reference data if the site is unreachable
         or returns fewer than 3 parseable rows.
    """
    logger.info("=== LLM Stats collection started ===")
    http = _build_session()

    live_models  = _scrape_live(http)
    use_fallback = live_models is None

    if not use_fallback and len(live_models) < 3:
        logger.warning(
            "Too few rows scraped from llm-stats.com (%d) — switching to fallback",
            len(live_models),
        )
        use_fallback = True

    model_list  = _REFERENCE_MODELS if use_fallback else live_models
    data_source = "reference data (fallback)" if use_fallback else "llm-stats.com (live)"

    saved, enriched = _upsert_models(model_list)

    logger.info("=== LLM Stats collection complete ===")
    logger.info("  Data source  : %s", data_source)
    logger.info("  Saved (new)  : %d", saved)
    logger.info("  Enriched     : %d", enriched)
    logger.info("  Total        : %d", saved + enriched)

    print(f"=== LLM Stats collection complete ===")
    print(f"  Data source  : {data_source}")
    print(f"  Saved (new)  : {saved}")
    print(f"  Enriched     : {enriched}")
    print(f"  Total        : {saved + enriched}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    collect()
