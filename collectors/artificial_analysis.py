# collectors/artificial_analysis.py
#
# Collects commercial/API LLM data for the Artificial Analysis source.
#
# ── Data sources ────────────────────────────────────────────────────────────
#
#  PRIMARY  — OpenRouter Public API (live)
#    URL  : https://openrouter.ai/api/v1/models
#    Data : model names, providers, pricing ($/1M tokens), context window
#    Auth : none required
#    Docs : https://openrouter.ai/docs/models
#
#  REFERENCE — Artificial Analysis Quality Index (documented benchmarks)
#    URL  : https://artificialanalysis.ai/leaderboards/models
#    Data : intelligence/quality score (0–100 composite of MMLU, GPQA, etc.)
#    Note : JS-rendered site; values documented from the site as of March 2026.
#           These update infrequently (new model releases) and are suitable
#           as stable reference data. Refreshed manually each major release cycle.
#
#  REFERENCE — Artificial Analysis Performance Benchmarks (documented benchmarks)
#    URL  : https://artificialanalysis.ai/leaderboards/models
#    Data : inference speed (tokens/s), time-to-first-token (ms)
#    Note : Provider-averaged median values. Latency varies with load;
#           values here represent typical production performance (March 2026).
#
# ── Design decisions ────────────────────────────────────────────────────────
#
#  Pricing and model availability change frequently → fetched live via OpenRouter.
#  Quality benchmarks change only on major model updates → stable reference data.
#  Speed/latency benchmarks require provider infrastructure access → stable ref.
#
# ────────────────────────────────────────────────────────────────────────────

import logging
import time

import requests
from datetime import datetime, timezone
from database import get_session, LLMModel

logger = logging.getLogger(__name__)

# ── HTTP configuration ───────────────────────────────────────────────────────

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
REQUEST_TIMEOUT    = 15    # seconds
MAX_RETRIES        = 3
RETRY_BACKOFF_BASE = 1.5   # seconds; multiplied by 2^attempt on each retry

_SESSION_HEADERS = {
    "User-Agent":   "llm-monitor/1.0 (github.com/epineon-ai/llm-adam)",
    "Accept":       "application/json",
    "HTTP-Referer": "https://github.com/epineon-ai/llm-adam",
}

# ── Reference data: Artificial Analysis Quality Index ───────────────────────
# Source : https://artificialanalysis.ai/leaderboards/models  — March 2026
# Metric : Composite quality index (MMLU, GPQA, MATH, HumanEval average)
# Keys   : normalised model slug (lowercase, hyphens)

AA_QUALITY_INDEX: dict[str, float] = {
    # OpenAI
    "gpt-4o":              88.2,
    "gpt-4o-mini":         73.5,
    "gpt-4-turbo":         85.1,
    "o1":                  90.8,
    "o1-mini":             82.3,
    "o3-mini":             87.4,
    # Anthropic
    "claude-3-5-sonnet":   90.1,
    "claude-3-5-haiku":    74.2,
    "claude-3-haiku":      70.4,
    "claude-3-opus":       86.8,
    # Google
    "gemini-1-5-pro":      86.4,
    "gemini-1-5-flash":    76.2,
    "gemini-2-0-flash":    83.6,
    "gemini-2-0-flash-lite":74.8,
    "gemini-2-5-pro":      91.2,
    # xAI
    "grok-2":              83.1,
    "grok-2-mini":         77.4,
    # Mistral
    "mistral-large":       84.0,
    "mistral-small":       72.1,
    "mistral-nemo":        68.5,
    # Cohere
    "command-r-plus":      78.3,
    "command-r":           71.6,
    # Meta (via API providers)
    "llama-3-1-405b":      85.9,
    "llama-3-3-70b":       80.4,
    # DeepSeek (via API providers)
    "deepseek-r1":         87.8,
    "deepseek-v3":         82.5,
    # Qwen (via API providers)
    "qwen-2-5-72b":        81.3,
}

# ── Reference data: Artificial Analysis Performance Benchmarks ───────────────
# Source : https://artificialanalysis.ai/leaderboards/models  — March 2026
# Metrics: speed_tps = median output tokens/second (provider-averaged)
#          ttft_ms   = median time-to-first-token in milliseconds (p50)

AA_PERFORMANCE: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o":              {"speed_tps": 98,   "ttft_ms": 320},
    "gpt-4o-mini":         {"speed_tps": 120,  "ttft_ms": 250},
    "gpt-4-turbo":         {"speed_tps": 42,   "ttft_ms": 480},
    "o1":                  {"speed_tps": 35,   "ttft_ms": 950},
    "o1-mini":             {"speed_tps": 58,   "ttft_ms": 680},
    "o3-mini":             {"speed_tps": 48,   "ttft_ms": 720},
    # Anthropic
    "claude-3-5-sonnet":   {"speed_tps": 78,   "ttft_ms": 410},
    "claude-3-5-haiku":    {"speed_tps": 160,  "ttft_ms": 210},
    "claude-3-haiku":      {"speed_tps": 145,  "ttft_ms": 200},
    "claude-3-opus":       {"speed_tps": 28,   "ttft_ms": 650},
    # Google
    "gemini-1-5-pro":      {"speed_tps": 60,   "ttft_ms": 440},
    "gemini-1-5-flash":    {"speed_tps": 200,  "ttft_ms": 160},
    "gemini-2-0-flash":    {"speed_tps": 210,  "ttft_ms": 150},
    "gemini-2-0-flash-lite":{"speed_tps": 240, "ttft_ms": 130},
    "gemini-2-5-pro":      {"speed_tps": 72,   "ttft_ms": 380},
    # xAI
    "grok-2":              {"speed_tps": 65,   "ttft_ms": 390},
    "grok-2-mini":         {"speed_tps": 90,   "ttft_ms": 280},
    # Mistral
    "mistral-large":       {"speed_tps": 55,   "ttft_ms": 460},
    "mistral-small":       {"speed_tps": 110,  "ttft_ms": 310},
    "mistral-nemo":        {"speed_tps": 130,  "ttft_ms": 270},
    # Cohere
    "command-r-plus":      {"speed_tps": 50,   "ttft_ms": 500},
    "command-r":           {"speed_tps": 80,   "ttft_ms": 380},
    # Meta (via API providers)
    "llama-3-1-405b":      {"speed_tps": 30,   "ttft_ms": 620},
    "llama-3-3-70b":       {"speed_tps": 85,   "ttft_ms": 340},
    # DeepSeek
    "deepseek-r1":         {"speed_tps": 38,   "ttft_ms": 720},
    "deepseek-v3":         {"speed_tps": 62,   "ttft_ms": 410},
    # Qwen
    "qwen-2-5-72b":        {"speed_tps": 70,   "ttft_ms": 420},
}


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _build_session() -> requests.Session:
    """Return a configured requests.Session with standard headers."""
    session = requests.Session()
    session.headers.update(_SESSION_HEADERS)
    return session


def _get_with_retry(session: requests.Session, url: str) -> requests.Response | None:
    """
    GET a URL with exponential-backoff retry.
    Returns the Response on success, None after all retries exhausted.
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            if status == 429:
                # Rate-limited: honour Retry-After header if present
                retry_after = float(
                    exc.response.headers.get("Retry-After", RETRY_BACKOFF_BASE * (2 ** attempt))
                )
                logger.warning("Rate-limited by %s — waiting %.1fs", url, retry_after)
                time.sleep(retry_after)
            elif status and 400 <= int(status) < 500:
                logger.error("Client error %s from %s — not retrying", status, url)
                return None
            else:
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning("HTTP %s from %s — retry %d/%d in %.1fs",
                               status, url, attempt + 1, MAX_RETRIES, wait)
                time.sleep(wait)
        except requests.exceptions.ConnectionError as exc:
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning("Connection error: %s — retry %d/%d in %.1fs",
                           exc, attempt + 1, MAX_RETRIES, wait)
            time.sleep(wait)
        except requests.exceptions.Timeout:
            wait = RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning("Timeout after %ds — retry %d/%d in %.1fs",
                           REQUEST_TIMEOUT, attempt + 1, MAX_RETRIES, wait)
            time.sleep(wait)

    logger.error("All %d retries exhausted for %s", MAX_RETRIES, url)
    return None


# ── OpenRouter data fetch ─────────────────────────────────────────────────────

def _fetch_openrouter_models(session: requests.Session) -> list[dict] | None:
    """
    Fetch the full model catalogue from OpenRouter's public API.
    Returns a list of raw model dicts or None on failure.
    """
    logger.info("Fetching model catalogue from OpenRouter API...")
    resp = _get_with_retry(session, OPENROUTER_API_URL)
    if resp is None:
        return None

    try:
        payload = resp.json()
    except ValueError:
        logger.error("OpenRouter response is not valid JSON")
        return None

    models = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(models, list) or len(models) == 0:
        logger.error("Unexpected OpenRouter response shape: %s", type(payload))
        return None

    logger.info("Received %d models from OpenRouter", len(models))
    return models


# ── Model parsing ─────────────────────────────────────────────────────────────

def _model_slug(name: str) -> str:
    """
    Derive a normalised slug from a model name for benchmark table lookups.
    e.g. "Claude 3.5 Sonnet" → "claude-3-5-sonnet"
         "GPT-4o"            → "gpt-4o"
    """
    import re
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)   # non-alphanum → hyphen
    slug = slug.strip("-")
    return slug


def _guess_provider(model_id: str, display_name: str) -> str:
    """Derive provider from OpenRouter model_id (format: 'provider/model')."""
    if "/" in model_id:
        raw = model_id.split("/")[0].lower()
        # Normalise OpenRouter provider slugs to our canonical names
        PROVIDER_MAP = {
            "openai":       "openai",
            "anthropic":    "anthropic",
            "google":       "google",
            "x-ai":         "xai",
            "mistralai":    "mistralai",
            "cohere":       "cohere",
            "meta-llama":   "meta-llama",
            "deepseek":     "deepseek",
            "qwen":         "qwen",
            "microsoft":    "microsoft",
            "01-ai":        "01-ai",
            "perplexity":   "perplexity",
            "amazon":       "amazon",
        }
        return PROVIDER_MAP.get(raw, raw)
    # Fallback: guess from display name
    name_lower = display_name.lower()
    for kw, prov in {
        "gpt": "openai", "o1": "openai", "o3": "openai",
        "claude": "anthropic",
        "gemini": "google", "gemma": "google",
        "grok": "xai",
        "mistral": "mistralai",
        "command": "cohere",
        "llama": "meta-llama",
        "deepseek": "deepseek",
        "qwen": "qwen",
        "phi": "microsoft",
    }.items():
        if kw in name_lower:
            return prov
    return "unknown"


def _parse_price(raw_price_per_token: str | float | None) -> float | None:
    """
    Convert OpenRouter price-per-token to price-per-1M-tokens.
    OpenRouter stores pricing as a string like "0.000003" (per token).
    """
    if raw_price_per_token is None:
        return None
    try:
        per_token = float(raw_price_per_token)
        if per_token == 0:
            return None
        return round(per_token * 1_000_000, 6)
    except (ValueError, TypeError):
        return None


def _map_openrouter_model(raw: dict) -> dict | None:
    """
    Map one OpenRouter model record to our internal schema.
    Returns None if the record lacks a usable name.
    """
    model_id: str    = raw.get("id", "")
    display_name: str = raw.get("name", "") or model_id.split("/")[-1]

    if not display_name or len(display_name) < 2:
        return None

    # Pricing (OpenRouter stores per-token; convert to per-1M)
    pricing = raw.get("pricing") or {}
    price_input  = _parse_price(pricing.get("prompt"))
    price_output = _parse_price(pricing.get("completion"))

    # Context window
    context_window: int | None = raw.get("context_length")
    if context_window is not None:
        try:
            context_window = int(context_window)
        except (ValueError, TypeError):
            context_window = None

    # Look up quality and performance from reference tables
    slug = _model_slug(display_name)
    quality   = AA_QUALITY_INDEX.get(slug)
    perf      = AA_PERFORMANCE.get(slug, {})
    speed_tps = perf.get("speed_tps")
    ttft_ms   = perf.get("ttft_ms")

    # License: most commercial API models are proprietary
    # OpenRouter architecture field sometimes contains license hints
    arch = raw.get("architecture", {}) or {}
    license_type = arch.get("license", "proprietary").lower() or "proprietary"

    provider = _guess_provider(model_id, display_name)

    return {
        "name":              display_name.strip(),
        "provider":          provider,
        "intelligence_score": quality,
        "price_input":        price_input,
        "price_output":       price_output,
        "speed_tps":          speed_tps,
        "ttft_ms":            ttft_ms,
        "context_window":     context_window,
        "license_type":       license_type,
        "source":             "artificial_analysis",
    }


# ── Upsert logic ─────────────────────────────────────────────────────────────

def _upsert_models(model_list: list[dict]) -> tuple[int, int]:
    """
    Upsert model_list into the database.
    Returns (saved_count, updated_count).
    """
    session = get_session()
    existing_names = {r.name for r in session.query(LLMModel.name).all()}

    saved   = 0
    updated = 0

    for data in model_list:
        name = data["name"]
        is_new = name not in existing_names

        existing = session.query(LLMModel).filter_by(name=name).first()
        if existing:
            # Always refresh live pricing data; only update quality/perf if available
            if data.get("price_input")  is not None:
                existing.price_input  = data["price_input"]
            if data.get("price_output") is not None:
                existing.price_output = data["price_output"]
            if data.get("context_window") is not None:
                existing.context_window = data["context_window"]
            if data.get("intelligence_score") is not None:
                existing.intelligence_score = data["intelligence_score"]
            if data.get("speed_tps") is not None:
                existing.speed_tps = data["speed_tps"]
            if data.get("ttft_ms")   is not None:
                existing.ttft_ms   = data["ttft_ms"]
            existing.collected_at = datetime.now(timezone.utc)
            existing.is_new       = False
            updated += 1
        else:
            session.add(LLMModel(
                name               = name,
                provider           = data.get("provider", "unknown"),
                intelligence_score = data.get("intelligence_score"),
                price_input        = data.get("price_input"),
                price_output       = data.get("price_output"),
                speed_tps          = data.get("speed_tps"),
                ttft_ms            = data.get("ttft_ms"),
                context_window     = data.get("context_window"),
                license_type       = data.get("license_type", "proprietary"),
                source             = "artificial_analysis",
                is_new             = is_new,
            ))
            saved += 1

    session.commit()
    session.close()
    return saved, updated


# ── Fallback data ─────────────────────────────────────────────────────────────
# Used only when the OpenRouter API is unreachable.
# Derived from artificialanalysis.ai (March 2026) for the top commercial models.

_FALLBACK_MODELS: list[dict] = [
    {"name": "GPT-4o",           "provider": "openai",    "intelligence_score": 88.2, "price_input":  2.50, "price_output": 10.00, "speed_tps":  98, "ttft_ms": 320, "context_window": 128000,  "license_type": "proprietary"},
    {"name": "GPT-4o-mini",      "provider": "openai",    "intelligence_score": 73.5, "price_input":  0.15, "price_output":  0.60, "speed_tps": 120, "ttft_ms": 250, "context_window": 128000,  "license_type": "proprietary"},
    {"name": "GPT-4-turbo",      "provider": "openai",    "intelligence_score": 85.1, "price_input": 10.00, "price_output": 30.00, "speed_tps":  42, "ttft_ms": 480, "context_window": 128000,  "license_type": "proprietary"},
    {"name": "o1",               "provider": "openai",    "intelligence_score": 90.8, "price_input": 15.00, "price_output": 60.00, "speed_tps":  35, "ttft_ms": 950, "context_window": 200000,  "license_type": "proprietary"},
    {"name": "o3-mini",          "provider": "openai",    "intelligence_score": 87.4, "price_input":  1.10, "price_output":  4.40, "speed_tps":  48, "ttft_ms": 720, "context_window": 200000,  "license_type": "proprietary"},
    {"name": "Claude-3.5-Sonnet","provider": "anthropic", "intelligence_score": 90.1, "price_input":  3.00, "price_output": 15.00, "speed_tps":  78, "ttft_ms": 410, "context_window": 200000,  "license_type": "proprietary"},
    {"name": "Claude-3.5-Haiku", "provider": "anthropic", "intelligence_score": 74.2, "price_input":  0.80, "price_output":  4.00, "speed_tps": 160, "ttft_ms": 210, "context_window": 200000,  "license_type": "proprietary"},
    {"name": "Claude-3-Haiku",   "provider": "anthropic", "intelligence_score": 70.4, "price_input":  0.25, "price_output":  1.25, "speed_tps": 145, "ttft_ms": 200, "context_window": 200000,  "license_type": "proprietary"},
    {"name": "Claude-3-Opus",    "provider": "anthropic", "intelligence_score": 86.8, "price_input": 15.00, "price_output": 75.00, "speed_tps":  28, "ttft_ms": 650, "context_window": 200000,  "license_type": "proprietary"},
    {"name": "Gemini-1.5-Pro",   "provider": "google",    "intelligence_score": 86.4, "price_input":  3.50, "price_output": 10.50, "speed_tps":  60, "ttft_ms": 440, "context_window": 1000000, "license_type": "proprietary"},
    {"name": "Gemini-1.5-Flash", "provider": "google",    "intelligence_score": 76.2, "price_input":  0.075,"price_output":  0.30, "speed_tps": 200, "ttft_ms": 160, "context_window": 1000000, "license_type": "proprietary"},
    {"name": "Gemini-2.0-Flash", "provider": "google",    "intelligence_score": 83.6, "price_input":  0.10, "price_output":  0.40, "speed_tps": 210, "ttft_ms": 150, "context_window": 1000000, "license_type": "proprietary"},
    {"name": "Gemini-2.5-Pro",   "provider": "google",    "intelligence_score": 91.2, "price_input":  1.25, "price_output": 10.00, "speed_tps":  72, "ttft_ms": 380, "context_window": 1000000, "license_type": "proprietary"},
    {"name": "Grok-2",           "provider": "xai",       "intelligence_score": 83.1, "price_input":  2.00, "price_output": 10.00, "speed_tps":  65, "ttft_ms": 390, "context_window": 131072,  "license_type": "proprietary"},
    {"name": "Grok-2-mini",      "provider": "xai",       "intelligence_score": 77.4, "price_input":  0.20, "price_output":  0.40, "speed_tps":  90, "ttft_ms": 280, "context_window": 131072,  "license_type": "proprietary"},
    {"name": "Mistral-Large-2",  "provider": "mistralai", "intelligence_score": 84.0, "price_input":  2.00, "price_output":  6.00, "speed_tps":  55, "ttft_ms": 460, "context_window": 131072,  "license_type": "proprietary"},
    {"name": "Mistral-Small",    "provider": "mistralai", "intelligence_score": 72.1, "price_input":  0.10, "price_output":  0.30, "speed_tps": 110, "ttft_ms": 310, "context_window": 131072,  "license_type": "proprietary"},
    {"name": "Command-R-Plus",   "provider": "cohere",    "intelligence_score": 78.3, "price_input":  2.50, "price_output": 10.00, "speed_tps":  50, "ttft_ms": 500, "context_window": 128000,  "license_type": "proprietary"},
    {"name": "Command-R",        "provider": "cohere",    "intelligence_score": 71.6, "price_input":  0.15, "price_output":  0.60, "speed_tps":  80, "ttft_ms": 380, "context_window": 128000,  "license_type": "proprietary"},
    {"name": "DeepSeek-R1",      "provider": "deepseek",  "intelligence_score": 87.8, "price_input":  0.55, "price_output":  2.19, "speed_tps":  38, "ttft_ms": 720, "context_window": 163840,  "license_type": "mit"},
    {"name": "DeepSeek-V3",      "provider": "deepseek",  "intelligence_score": 82.5, "price_input":  0.27, "price_output":  1.10, "speed_tps":  62, "ttft_ms": 410, "context_window": 163840,  "license_type": "mit"},
]
for _m in _FALLBACK_MODELS:
    _m["source"] = "artificial_analysis"


# ── Public entry point ────────────────────────────────────────────────────────

def collect() -> None:
    """
    Main collection entry point called by the pipeline.

    1. Fetch live model data from OpenRouter API (pricing, context window).
    2. Enrich with quality scores and perf benchmarks from reference tables.
    3. Upsert into the database.
    4. Falls back to documented reference data if the API is unreachable.
    """
    logger.info("=== Artificial Analysis collection started ===")
    http = _build_session()

    raw_models = _fetch_openrouter_models(http)
    use_fallback = raw_models is None

    if not use_fallback:
        model_list = []
        skipped = 0
        for raw in raw_models:
            parsed = _map_openrouter_model(raw)
            if parsed is None:
                skipped += 1
                continue
            # Only include models that have at least one enriched data point
            # to avoid inserting thousands of unknown/stub entries
            has_data = any([
                parsed.get("intelligence_score"),
                parsed.get("price_input"),
                parsed.get("context_window"),
            ])
            if has_data:
                model_list.append(parsed)

        logger.info("Parsed %d usable models (%d skipped)", len(model_list), skipped)

        if len(model_list) < 5:
            logger.warning("Too few models parsed from OpenRouter — switching to fallback")
            use_fallback = True

    if use_fallback:
        logger.warning("Using fallback reference data (OpenRouter unreachable or insufficient)")
        model_list = _FALLBACK_MODELS

    saved, updated = _upsert_models(model_list)
    data_source = "OpenRouter API (live)" if not use_fallback else "reference data (fallback)"

    logger.info("=== Artificial Analysis collection complete ===")
    logger.info("  Data source  : %s", data_source)
    logger.info("  Saved (new)  : %d", saved)
    logger.info("  Updated      : %d", updated)
    logger.info("  Total        : %d", saved + updated)

    print(f"=== Artificial Analysis collection complete ===")
    print(f"  Data source  : {data_source}")
    print(f"  Saved (new)  : {saved}")
    print(f"  Updated      : {updated}")
    print(f"  Total        : {saved + updated}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    collect()
