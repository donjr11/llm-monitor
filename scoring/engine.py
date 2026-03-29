# scoring/engine.py
# TOPSIS and AHP+TOPSIS composite scoring and recommendation engine.
#
# TOPSIS steps implemented:
#   1. Load normalized metrics from DB
#   2. Build weighted matrix (norm_value * weight)
#   3. Find ideal best (V+) and ideal worst (V-) per metric
#   4. Compute Euclidean distance from V+ and V- for each model
#   5. Compute final score = D- / (D+ + D-)
#   6. Rank models by score descending
#
# AHP+TOPSIS:
#   Same as above but weights are derived from AHP pairwise matrices
#   instead of being manually set in profiles.py

import math
from database import get_session, LLMModel, ScoringRun
from scoring.profiles import PROFILES, get_profile
from datetime import datetime, timezone

# License types not allowed for commercial use
NON_COMMERCIAL_LICENSES = {
    "llama-community",
    "gemma",
    "cc-by-nc",
    "cc-by-nc-4.0",
    "unknown",
}


def is_commercial_safe(license_type: str) -> bool:
    """Return True if model license allows commercial use."""
    if not license_type:
        return False
    return license_type.lower() not in NON_COMMERCIAL_LICENSES


def get_weighted_matrix(models: list, weights: dict) -> list[dict]:
    """
    TOPSIS Step 2: multiply each normalized metric by its weight.
    Returns list of dicts with model name + weighted metric values.
    Skips models missing more than 2 metrics.
    """
    matrix = []
    for model in models:
        row = {"name": model.name, "_model": model}
        missing = 0
        for metric, weight in weights.items():
            value = getattr(model, metric, None)
            if value is None:
                missing += 1
                row[metric] = 0.0
            else:
                row[metric] = value * weight
        if missing <= 2:
            matrix.append(row)
    return matrix


def get_ideal_solutions(matrix: list, weights: dict) -> tuple[dict, dict]:
    """
    TOPSIS Step 3: find ideal best (V+) and ideal worst (V-).
    V+ = max weighted value per metric across all models.
    V- = min weighted value per metric across all models.
    """
    v_plus  = {}
    v_minus = {}
    for metric in weights:
        values = [row[metric] for row in matrix]
        v_plus[metric]  = max(values)
        v_minus[metric] = min(values)
    return v_plus, v_minus


def euclidean_distance(row: dict, ideal: dict, weights: dict) -> float:
    """
    TOPSIS Step 4: Euclidean distance between a model row and an ideal point.
    distance = sqrt( sum( (weighted_value - ideal_value)^2 ) )
    """
    total = 0.0
    for metric in weights:
        diff = row[metric] - ideal[metric]
        total += diff ** 2
    return math.sqrt(total)


def topsis_score(d_plus: float, d_minus: float) -> float:
    """
    TOPSIS Step 5: final score = D- / (D+ + D-)
    Score of 1.0 = identical to ideal best.
    Score of 0.0 = identical to ideal worst.
    """
    total = d_plus + d_minus
    if total == 0:
        return 0.0
    return round(d_minus / total, 4)


def build_justification(model: LLMModel, profile_name: str,
                        weights: dict, score: float,
                        v_plus: dict, v_minus: dict) -> str:
    """Generate human-readable justification for a recommendation."""

    best_metric = None
    best_gap    = float("inf")
    for metric, weight in weights.items():
        if weight == 0:
            continue
        value = getattr(model, metric, None)
        if value is None:
            continue
        weighted_val = value * weight
        gap = abs(weighted_val - v_plus[metric])
        if gap < best_gap:
            best_gap    = gap
            best_metric = metric

    metric_labels = {
        "norm_intelligence": f"intelligence ({model.intelligence_score:.1f}/100)" if model.intelligence_score else "intelligence",
        "norm_speed":        f"speed ({model.speed_tps:.0f} tok/s)" if model.speed_tps else "speed",
        "norm_price":        f"cost efficiency (${model.price_input:.3f}/1M tokens)" if model.price_input else "cost",
        "norm_context":      f"context window ({model.context_window:,} tokens)" if model.context_window else "context",
        "norm_ttft":         f"low latency ({model.ttft_ms:.0f}ms TTFT)" if model.ttft_ms else "latency",
    }

    profile_context = {
        "coding":            "software development",
        "reasoning":         "complex analytical workloads",
        "rag_long_context":  "long-context RAG pipelines",
        "minimum_cost":      "high-volume cost-sensitive workloads",
        "enterprise_agents": "autonomous agent pipelines",
    }

    best_label = metric_labels.get(best_metric, best_metric) if best_metric else "overall balance"
    context    = profile_context.get(profile_name, profile_name)

    return (
        f"{model.name} achieves a TOPSIS score of {score:.3f} for {context}, "
        f"ranking closest to the ideal solution in {best_label}. "
        f"License: {model.license_type or 'unknown'}."
    )


def recommend(profile_name: str,
              commercial: bool = False,
              top_n: int = 3,
              method: str = "ahp_topsis") -> dict:
    """
    Main TOPSIS / AHP+TOPSIS recommendation function.

    Args:
        profile_name : one of the keys in PROFILES
        commercial   : if True, exclude non-commercial licenses
        top_n        : number of top models to return
        method       : "topsis" (manual weights) or "ahp_topsis" (AHP-derived)

    Returns a dict with profile info, top results, and full ranking.
    """
    profile = get_profile(profile_name)
    if not profile:
        return {
            "error": f"Unknown profile '{profile_name}'. "
                     f"Available: {list(PROFILES.keys())}"
        }

    # ── Weight selection: AHP+TOPSIS or standard TOPSIS ──
    cr = None
    if method == "ahp_topsis":
        from scoring.ahp import get_ahp_weights
        ahp_result = get_ahp_weights(profile_name)
        if ahp_result is None:
            return {"error": f"No AHP matrix defined for profile '{profile_name}'"}
        weights, cr = ahp_result
    else:
        weights = profile["weights"]

    session = get_session()
    models  = session.query(LLMModel).all()

    # ── Compliance filter ──
    filtered_models    = []
    skipped_compliance = 0
    for model in models:
        if commercial and not is_commercial_safe(model.license_type):
            skipped_compliance += 1
            continue
        filtered_models.append(model)

    if not filtered_models:
        session.close()
        return {"error": "No models passed the compliance filter."}

    # ── TOPSIS Step 2: weighted matrix ──
    matrix = get_weighted_matrix(filtered_models, weights)

    # ── TOPSIS Step 3: ideal best and worst ──
    v_plus, v_minus = get_ideal_solutions(matrix, weights)

    # ── TOPSIS Steps 4 & 5: distances and scores ──
    scored = []
    for row in matrix:
        model   = row["_model"]
        d_plus  = euclidean_distance(row, v_plus,  weights)
        d_minus = euclidean_distance(row, v_minus, weights)
        score   = topsis_score(d_plus, d_minus)

        scored.append({
            "name":           model.name,
            "provider":       model.provider,
            "score":          score,
            "d_plus":         round(d_plus,  4),
            "d_minus":        round(d_minus, 4),
            "intelligence":   model.intelligence_score,
            "price_input":    model.price_input,
            "price_output":   model.price_output,
            "speed_tps":      model.speed_tps,
            "ttft_ms":        model.ttft_ms,
            "context_window": model.context_window,
            "license_type":   model.license_type,
            "source":         model.source,
            "is_new":         model.is_new,
        })

    # ── Step 6: rank descending ──
    scored.sort(key=lambda x: x["score"], reverse=True)

    # ── Save top-N to scoring_runs table ──
    run_at = datetime.now(timezone.utc)
    for rank, item in enumerate(scored[:top_n], start=1):
        session.add(ScoringRun(
            run_at     = run_at,
            profile    = profile_name,
            model_name = item["name"],
            score      = item["score"],
            rank       = rank,
        ))
    session.commit()

    # ── Build top-N results with justification ──
    top_results = []
    for rank, item in enumerate(scored[:top_n], start=1):
        model = next(m for m in filtered_models if m.name == item["name"])
        top_results.append({
            "rank":          rank,
            "name":          item["name"],
            "provider":      item["provider"],
            "score":         item["score"],
            "d_plus":        item["d_plus"],
            "d_minus":       item["d_minus"],
            "justification": build_justification(
                                 model, profile_name,
                                 weights, item["score"],
                                 v_plus, v_minus
                             ),
            "metrics": {
                "intelligence":   item["intelligence"],
                "price_input":    item["price_input"],
                "price_output":   item["price_output"],
                "speed_tps":      item["speed_tps"],
                "ttft_ms":        item["ttft_ms"],
                "context_window": item["context_window"],
                "license":        item["license_type"],
            }
        })

    session.close()

    return {
        "profile":           profile_name,
        "description":       profile["description"],
        "weights":           weights,
        "method":            method.upper().replace("_", "+"),
        "consistency_ratio": cr,
        "commercial_filter": commercial,
        "models_skipped":    skipped_compliance,
        "total_scored":      len(scored),
        "ideal_best":        v_plus,
        "ideal_worst":       v_minus,
        "results":           top_results,
        "all_scored":        scored,
    }


def score_all_profiles() -> dict:
    """Run scoring for all profiles. Used by dashboard and report."""
    results = {}
    for profile_name in PROFILES:
        results[profile_name] = recommend(profile_name, commercial=False)
    return results


if __name__ == "__main__":
    import json
    print("🧪 Testing AHP+TOPSIS scoring engine...\n")

    for m in ["topsis", "ahp_topsis"]:
        print(f"── Method: {m.upper()} ──")
        result = recommend("coding", commercial=True, method=m)
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"Weights : {result['weights']}")
            if result['consistency_ratio']:
                print(f"CR      : {result['consistency_ratio']}")
            print(f"Top 3:")
            for r in result["results"]:
                print(f"  #{r['rank']} {r['name']} — {r['score']}")
        print()