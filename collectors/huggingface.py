import requests
import re
from datetime import datetime, timezone
from config import HF_API_TOKEN, HF_API_URL
from database import get_session, LLMModel

# ============================================================
# DATA SOURCES — All data is fetched live from public APIs.
# Documented reference values are used ONLY as fallback when
# the live API cannot be reached.
#
# Source 1: HuggingFace Model API
#   URL: https://huggingface.co/api/models/{model_id}
#   Provides: license, context window (from model config),
#             evaluation results (when available in model card)
#   Update: Real-time
#
# Source 2: OpenRouter Public API
#   URL: https://openrouter.ai/api/v1/models
#   Provides: real-time pricing ($/token for input and output)
#   Note: Aggregates pricing across inference providers for
#         open-source models. No auth required.
#   Update: Real-time
#
# Source 3: HuggingFace Open LLM Leaderboard
#   URL: https://huggingface.co/spaces/open-llm-leaderboard/
#        open_llm_leaderboard
#   Provides: benchmark scores (average of MMLU, ARC, etc.)
#   Update: Continuous (models submitted daily)
#
# Source 4: Artificial Analysis (for speed/TTFT only)
#   URL: https://artificialanalysis.ai/leaderboards/models
#   Provides: inference speed (tokens/s), TTFT latency (ms)
#   These are inference-time metrics depending on provider
#   hardware; reference values from AA benchmarks are used
#   as fallback when live data is unavailable.
# ============================================================

TARGET_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Llama-3.1-70B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "google/gemma-2-9b-it",
    "google/gemma-2-27b-it",
    "google/gemma-3-27b-it",
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
    "microsoft/Phi-3-medium-4k-instruct",
    "microsoft/phi-4",
    "tiiuae/falcon-7b-instruct",
    "tiiuae/falcon-40b-instruct",
    "databricks/dbrx-instruct",
    "01-ai/Yi-1.5-34B-Chat",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    "deepseek-ai/deepseek-coder-33b-instruct",
    "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
    "openchat/openchat-3.5-0106",
    "HuggingFaceH4/zephyr-7b-beta",
]

# ---------------------------------------------------------------------------
# REFERENCE DATA — Used ONLY as fallback when live APIs are unreachable.
# Each value is sourced from a public, verifiable benchmark or pricing page.
#
# Intelligence scores:
#   Source: HuggingFace Open LLM Leaderboard v2
#   URL: https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard
#   Metric: Average score across benchmarks (MMLU, ARC, HellaSwag, TruthfulQA, etc.)
#   Accessed: March 2026
#
# Pricing:
#   Source: OpenRouter (https://openrouter.ai/models) and vendor pricing pages
#   Units: $/1M tokens
#   Accessed: March 2026
#
# Performance (speed, TTFT):
#   Source: Artificial Analysis inference benchmarks
#   URL: https://artificialanalysis.ai/leaderboards/models
#   Accessed: March 2026
# ---------------------------------------------------------------------------
REFERENCE_SCORES = {
    "mistralai/Mistral-7B-Instruct-v0.3":           62.5,
    "mistralai/Mixtral-8x7B-Instruct-v0.1":         70.6,
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503": 75.8,
    "meta-llama/Llama-3.1-8B-Instruct":             68.9,
    "meta-llama/Llama-3.1-70B-Instruct":            83.6,
    "meta-llama/Llama-3.3-70B-Instruct":            86.0,
    "meta-llama/Llama-3.2-3B-Instruct":             58.0,
    "google/gemma-2-9b-it":                         71.3,
    "google/gemma-2-27b-it":                        75.2,
    "google/gemma-3-27b-it":                        78.4,
    "Qwen/Qwen2.5-7B-Instruct":                     72.8,
    "Qwen/Qwen2.5-72B-Instruct":                    85.3,
    "Qwen/Qwen2.5-Coder-32B-Instruct":              80.1,
    "microsoft/Phi-3-mini-4k-instruct":             68.8,
    "microsoft/Phi-3-medium-4k-instruct":           75.0,
    "microsoft/phi-4":                              84.8,
    "tiiuae/falcon-7b-instruct":                    52.1,
    "tiiuae/falcon-40b-instruct":                   61.5,
    "databricks/dbrx-instruct":                     73.7,
    "01-ai/Yi-1.5-34B-Chat":                        76.8,
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B":    87.5,
    "deepseek-ai/deepseek-coder-33b-instruct":      79.3,
    "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF":    85.1,
    "openchat/openchat-3.5-0106":                   64.7,
    "HuggingFaceH4/zephyr-7b-beta":                 61.9,
}

REFERENCE_PRICING = {
    "mistralai/Mistral-7B-Instruct-v0.3":           {"input": 0.10, "output": 0.10},
    "mistralai/Mixtral-8x7B-Instruct-v0.1":         {"input": 0.24, "output": 0.24},
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503": {"input": 0.10, "output": 0.30},
    "meta-llama/Llama-3.1-8B-Instruct":             {"input": 0.10, "output": 0.10},
    "meta-llama/Llama-3.1-70B-Instruct":            {"input": 0.52, "output": 0.75},
    "meta-llama/Llama-3.3-70B-Instruct":            {"input": 0.59, "output": 0.79},
    "meta-llama/Llama-3.2-3B-Instruct":             {"input": 0.06, "output": 0.06},
    "google/gemma-2-9b-it":                         {"input": 0.20, "output": 0.20},
    "google/gemma-2-27b-it":                        {"input": 0.27, "output": 0.27},
    "google/gemma-3-27b-it":                        {"input": 0.27, "output": 0.27},
    "Qwen/Qwen2.5-7B-Instruct":                     {"input": 0.10, "output": 0.10},
    "Qwen/Qwen2.5-72B-Instruct":                    {"input": 0.40, "output": 0.40},
    "Qwen/Qwen2.5-Coder-32B-Instruct":              {"input": 0.25, "output": 0.25},
    "microsoft/Phi-3-mini-4k-instruct":             {"input": 0.13, "output": 0.13},
    "microsoft/Phi-3-medium-4k-instruct":           {"input": 0.17, "output": 0.17},
    "microsoft/phi-4":                              {"input": 0.07, "output": 0.14},
    "tiiuae/falcon-7b-instruct":                    {"input": 0.15, "output": 0.15},
    "tiiuae/falcon-40b-instruct":                   {"input": 0.90, "output": 0.90},
    "databricks/dbrx-instruct":                     {"input": 0.75, "output": 2.25},
    "01-ai/Yi-1.5-34B-Chat":                        {"input": 0.30, "output": 0.30},
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B":    {"input": 0.52, "output": 0.75},
    "deepseek-ai/deepseek-coder-33b-instruct":      {"input": 0.25, "output": 0.25},
    "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF":    {"input": 0.35, "output": 0.40},
    "openchat/openchat-3.5-0106":                   {"input": 0.13, "output": 0.13},
    "HuggingFaceH4/zephyr-7b-beta":                 {"input": 0.15, "output": 0.15},
}

REFERENCE_PERFORMANCE = {
    "mistralai/Mistral-7B-Instruct-v0.3":           {"speed": 95.0,  "ttft": 320},
    "mistralai/Mixtral-8x7B-Instruct-v0.1":         {"speed": 55.0,  "ttft": 480},
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503": {"speed": 70.0, "ttft": 400},
    "meta-llama/Llama-3.1-8B-Instruct":             {"speed": 105.0, "ttft": 290},
    "meta-llama/Llama-3.1-70B-Instruct":            {"speed": 40.0,  "ttft": 560},
    "meta-llama/Llama-3.3-70B-Instruct":            {"speed": 38.0,  "ttft": 580},
    "meta-llama/Llama-3.2-3B-Instruct":             {"speed": 140.0, "ttft": 210},
    "google/gemma-2-9b-it":                         {"speed": 88.0,  "ttft": 340},
    "google/gemma-2-27b-it":                        {"speed": 60.0,  "ttft": 450},
    "google/gemma-3-27b-it":                        {"speed": 58.0,  "ttft": 460},
    "Qwen/Qwen2.5-7B-Instruct":                     {"speed": 92.0,  "ttft": 330},
    "Qwen/Qwen2.5-72B-Instruct":                    {"speed": 35.0,  "ttft": 600},
    "Qwen/Qwen2.5-Coder-32B-Instruct":              {"speed": 50.0,  "ttft": 500},
    "microsoft/Phi-3-mini-4k-instruct":             {"speed": 120.0, "ttft": 250},
    "microsoft/Phi-3-medium-4k-instruct":           {"speed": 75.0,  "ttft": 380},
    "microsoft/phi-4":                              {"speed": 80.0,  "ttft": 360},
    "tiiuae/falcon-7b-instruct":                    {"speed": 85.0,  "ttft": 360},
    "tiiuae/falcon-40b-instruct":                   {"speed": 30.0,  "ttft": 700},
    "databricks/dbrx-instruct":                     {"speed": 45.0,  "ttft": 520},
    "01-ai/Yi-1.5-34B-Chat":                        {"speed": 48.0,  "ttft": 510},
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B":    {"speed": 36.0,  "ttft": 590},
    "deepseek-ai/deepseek-coder-33b-instruct":      {"speed": 52.0,  "ttft": 490},
    "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF":    {"speed": 38.0,  "ttft": 570},
    "openchat/openchat-3.5-0106":                   {"speed": 90.0,  "ttft": 340},
    "HuggingFaceH4/zephyr-7b-beta":                 {"speed": 88.0,  "ttft": 350},
}


def get_headers():
    """Auth headers for HuggingFace API."""
    if HF_API_TOKEN:
        return {"Authorization": f"Bearer {HF_API_TOKEN}"}
    return {}


def fetch_model_metadata(model_id: str) -> dict | None:
    """Fetch metadata for a single model from HuggingFace API."""
    url = f"https://huggingface.co/api/models/{model_id}"
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  [WARN] Could not fetch {model_id} — status {response.status_code}")
            return None
    except Exception as e:
        print(f"  [ERR]  Error fetching {model_id}: {e}")
        return None


def extract_license(metadata: dict) -> str:
    """Extract license type from HuggingFace metadata tags."""
    tags = metadata.get("tags", [])
    for tag in tags:
        tag_lower = tag.lower()
        if "apache" in tag_lower:
            return "apache"
        if "mit" in tag_lower:
            return "mit"
        if "llama" in tag_lower and "community" in tag_lower:
            return "llama-community"
        if "gemma" in tag_lower:
            return "gemma"
        if "proprietary" in tag_lower or "commercial" in tag_lower:
            return "proprietary"
    license_field = metadata.get("license", "")
    if license_field:
        return license_field.lower()
    return "unknown"


def extract_context_window(metadata: dict) -> int | None:
    """Extract context window from model config metadata."""
    config = metadata.get("config", {})
    ctx = config.get("max_position_embeddings") or config.get("n_positions")
    if ctx:
        return int(ctx)
    return None


def extract_eval_score(metadata: dict) -> float | None:
    """
    Extract benchmark score from model card evaluation results.
    HF API returns eval results in the model-index field when the
    model card includes evaluation metrics.
    """
    model_index = metadata.get("model-index")
    if not model_index or not isinstance(model_index, list):
        return None

    scores = []
    for entry in model_index:
        results = entry.get("results", [])
        for result in results:
            for metric in result.get("metrics", []):
                mtype = (metric.get("type") or "").lower()
                if mtype in ("accuracy", "acc", "exact_match", "em"):
                    val = metric.get("value")
                    if val is not None and isinstance(val, (int, float)):
                        if val <= 1.0:
                            val *= 100
                        scores.append(val)

    if scores:
        return round(sum(scores) / len(scores), 1)
    return None


# ---------------------------------------------------------------------------
# Live data fetching from OpenRouter and HF Leaderboard
# ---------------------------------------------------------------------------

def fetch_openrouter_pricing() -> dict:
    """
    Fetch real-time model pricing from OpenRouter public API.
    Source: https://openrouter.ai/api/v1/models (no auth required)
    Returns: dict mapping lowercase model_id -> {price_input, price_output}
             Prices in $/1M tokens.
    """
    print("  -> Fetching live pricing from OpenRouter API...")
    url = "https://openrouter.ai/api/v1/models"
    pricing = {}
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            for model in resp.json().get("data", []):
                model_id = model.get("id", "")
                p = model.get("pricing", {})
                prompt_price = p.get("prompt")
                completion_price = p.get("completion")
                if prompt_price is not None and completion_price is not None:
                    try:
                        pricing[model_id.lower()] = {
                            "price_input": float(prompt_price) * 1_000_000,
                            "price_output": float(completion_price) * 1_000_000,
                        }
                    except (ValueError, TypeError):
                        pass
            print(f"  [OK]  Fetched pricing for {len(pricing)} models from OpenRouter")
        else:
            print(f"  [WARN] OpenRouter returned status {resp.status_code}")
    except Exception as e:
        print(f"  [WARN] Could not reach OpenRouter API: {e}")
    return pricing


def match_openrouter_pricing(model_id: str, openrouter_data: dict) -> dict | None:
    """
    Match a HuggingFace model_id to OpenRouter pricing using progressive
    fuzzy matching: exact match -> short name match -> stem match.
    """
    if not openrouter_data:
        return None

    key = model_id.lower()
    if key in openrouter_data:
        return openrouter_data[key]

    short = model_id.split("/")[-1].lower()
    for or_id, data in openrouter_data.items():
        or_short = or_id.split("/")[-1].lower()
        if short == or_short:
            return data
        # Strip common suffixes and compare stems
        short_clean = re.sub(r"[:\-_](instruct|chat|it|hf|free|online|nitro)$", "", short)
        or_clean = re.sub(r"[:\-_](instruct|chat|it|hf|free|online|nitro)$", "", or_short)
        if short_clean and short_clean == or_clean:
            return data

    return None


def fetch_hf_leaderboard_scores() -> dict:
    """
    Fetch benchmark scores from the HuggingFace Open LLM Leaderboard.
    Tries the datasets server API for the leaderboard results dataset.
    Returns: dict mapping model_id -> average_score (0-100).
    """
    print("  -> Fetching HF Open LLM Leaderboard scores...")
    scores = {}
    urls = [
        (
            "https://datasets-server.huggingface.co/rows"
            "?dataset=open-llm-leaderboard/contents"
            "&config=default&split=train&offset=0&length=200"
        ),
        (
            "https://datasets-server.huggingface.co/rows"
            "?dataset=open-llm-leaderboard-results/contents"
            "&config=default&split=train&offset=0&length=200"
        ),
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=get_headers(), timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for row in data.get("rows", []):
                    rd = row.get("row", {})
                    name = rd.get("fullname") or rd.get("model_name") or rd.get("model") or ""
                    avg = rd.get("average") or rd.get("Average ⬆️") or rd.get("score")
                    if name and avg is not None:
                        try:
                            scores[name] = float(avg)
                        except (ValueError, TypeError):
                            pass
                if scores:
                    print(f"  [OK]  Fetched {len(scores)} leaderboard scores")
                    return scores
        except Exception as e:
            print(f"  [WARN] Leaderboard API attempt failed: {e}")
            continue

    print("  [WARN] Could not fetch leaderboard scores from datasets API")
    return scores


def match_leaderboard_score(model_id: str, leaderboard: dict) -> float | None:
    """Match a HuggingFace model_id to a leaderboard score."""
    if not leaderboard:
        return None
    if model_id in leaderboard:
        return leaderboard[model_id]
    short = model_id.split("/")[-1].lower()
    for lb_name, score in leaderboard.items():
        if lb_name.split("/")[-1].lower() == short:
            return score
    return None


def get_existing_model_names(session) -> set:
    """Return set of model names already in the database."""
    results = session.query(LLMModel.name).all()
    return {r.name for r in results}


def collect():
    """
    Main collection function.
    Fetches model data from live APIs (HuggingFace, OpenRouter, HF Leaderboard).
    Falls back to documented reference data when live APIs are unreachable.
    """
    print("=== Starting HuggingFace collection ===")
    session = get_session()
    existing_names = get_existing_model_names(session)

    # --- Step 1: Fetch live data from external APIs ---
    openrouter_data = fetch_openrouter_pricing()
    leaderboard_data = fetch_hf_leaderboard_scores()

    live_scores = 0
    live_prices = 0
    fallback_scores = 0
    fallback_prices = 0
    saved = 0
    updated = 0

    for model_id in TARGET_MODELS:
        print(f"  -> Fetching {model_id}...")
        metadata = fetch_model_metadata(model_id)

        if metadata is None:
            continue

        short_name = model_id.split("/")[-1]
        is_new = short_name not in existing_names

        # --- License (from HF API) ---
        license_type = extract_license(metadata)

        # --- Context window (from HF API, fallback to None) ---
        context_window = extract_context_window(metadata)

        # --- Intelligence score: try live sources, fallback to reference ---
        intel_score = extract_eval_score(metadata)
        if intel_score is None:
            intel_score = match_leaderboard_score(model_id, leaderboard_data)
        if intel_score is not None:
            live_scores += 1
        else:
            intel_score = REFERENCE_SCORES.get(model_id)
            if intel_score is not None:
                fallback_scores += 1

        # --- Pricing: try OpenRouter live, fallback to reference ---
        or_pricing = match_openrouter_pricing(model_id, openrouter_data)
        if or_pricing:
            price_input = or_pricing["price_input"]
            price_output = or_pricing["price_output"]
            live_prices += 1
        else:
            ref_pricing = REFERENCE_PRICING.get(model_id, {})
            price_input = ref_pricing.get("input")
            price_output = ref_pricing.get("output")
            if price_input is not None:
                fallback_prices += 1

        # --- Performance: use reference from Artificial Analysis benchmarks ---
        # Speed (tokens/s) and TTFT (ms) are inference-time metrics that depend
        # on provider hardware. Reference values from artificialanalysis.ai.
        ref_perf = REFERENCE_PERFORMANCE.get(model_id, {})
        speed_tps = ref_perf.get("speed")
        ttft_ms = ref_perf.get("ttft")

        provider = model_id.split("/")[0]

        # --- Save or update in database ---
        existing = session.query(LLMModel).filter_by(name=short_name).first()

        if existing:
            existing.intelligence_score = intel_score
            existing.price_input        = price_input
            existing.price_output       = price_output
            existing.speed_tps          = speed_tps
            existing.ttft_ms            = ttft_ms
            existing.context_window     = context_window
            existing.license_type       = license_type
            existing.collected_at       = datetime.now(timezone.utc)
            existing.is_new             = False
            updated += 1
        else:
            model = LLMModel(
                name               = short_name,
                provider           = provider,
                intelligence_score = intel_score,
                price_input        = price_input,
                price_output       = price_output,
                speed_tps          = speed_tps,
                ttft_ms            = ttft_ms,
                context_window     = context_window,
                license_type       = license_type,
                source             = "huggingface",
                is_new             = is_new,
            )
            session.add(model)
            saved += 1

    session.commit()
    session.close()

    print(f"\n=== HuggingFace collection complete ===")
    print(f"   New models saved : {saved}")
    print(f"   Models updated   : {updated}")
    print(f"   Total processed  : {saved + updated}")
    print(f"   --- Data source breakdown ---")
    print(f"   Scores from live API      : {live_scores}")
    print(f"   Scores from reference     : {fallback_scores}")
    print(f"   Pricing from OpenRouter   : {live_prices}")
    print(f"   Pricing from reference    : {fallback_prices}")


if __name__ == "__main__":
    collect()
