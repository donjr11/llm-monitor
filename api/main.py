# api/main.py
# FastAPI REST API for the LLM Monitoring System.
#
# Endpoints:
#   GET /                          → health check
#   GET /models                    → list all models
#   GET /models/new                → models flagged as new
#   GET /profiles                  → list available profiles
#   GET /recommend                 → AHP+TOPSIS recommendation
#   POST /collect                  → trigger full collection pipeline
#   GET /report/generate           → generate digest report

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from database import get_session, LLMModel, init_db
from scoring.engine import recommend, score_all_profiles
from scoring.profiles import list_profiles, PROFILES

# ─────────────────────────────────────────
# AUTO-INIT ON STARTUP
# ─────────────────────────────────────────

init_db()

# is_new is a transient flag: meaningful only during the collection run that
# first discovered a model.  Clear stale flags on every restart so the
# dashboard never shows previously-known models as "new".
# A /collect call will re-set is_new=True only for genuinely new models.
_startup_session = get_session()
_count = _startup_session.query(LLMModel).count()
_startup_session.query(LLMModel).update({"is_new": False})
_startup_session.commit()
_startup_session.close()

if _count == 0:
    print("📦 Empty database detected — running initial collection...")
    from collectors.huggingface         import collect as _hf
    from collectors.artificial_analysis import collect as _aa
    from collectors.llmstats            import collect as _ls
    from collectors.normalizer          import normalize_all as _norm
    _hf()
    _aa()
    _ls()
    _norm()
    print("✅ Initial collection complete.")

# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────

app = FastAPI(
    title="LLM Monitoring System",
    description=(
        "Automated pipeline for collecting, scoring, and recommending "
        "LLMs by enterprise profile. Scoring uses AHP+TOPSIS (Multi-Criteria "
        "Decision Analysis)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status":  "ok",
        "service": "LLM Monitoring System",
        "version": "1.0.0",
        "method":  "AHP+TOPSIS",
    }


# ─────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────

@app.get("/models")
def get_models(
    source:   Optional[str] = Query(None, description="Filter by source: huggingface, artificial_analysis, llm_stats"),
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    license:  Optional[str] = Query(None, description="Filter by license type"),
):
    """Return all models in the database with optional filters."""
    session = get_session()
    query   = session.query(LLMModel)

    if source:
        query = query.filter(LLMModel.source == source)
    if provider:
        query = query.filter(LLMModel.provider.ilike(f"%{provider}%"))
    if license:
        query = query.filter(LLMModel.license_type == license)

    models = query.all()
    session.close()

    return {
        "total":  len(models),
        "models": [serialize_model(m) for m in models],
    }


@app.get("/models/new")
def get_new_models():
    """Return models flagged as new in the latest collection run."""
    session = get_session()
    models  = session.query(LLMModel).filter(LLMModel.is_new == True).all()
    session.close()

    return {
        "total":  len(models),
        "models": [serialize_model(m) for m in models],
    }


@app.get("/models/{model_name}")
def get_model(model_name: str):
    """Return a single model by name."""
    session = get_session()
    model   = session.query(LLMModel).filter(
        LLMModel.name.ilike(f"%{model_name}%")
    ).first()
    session.close()

    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found."
        )
    return serialize_model(model)


# ─────────────────────────────────────────
# PROFILES
# ─────────────────────────────────────────

@app.get("/profiles")
def get_profiles():
    """Return all available enterprise profiles with descriptions and weights."""
    from scoring.ahp import get_ahp_weights
    profiles_out = []
    for name, data in PROFILES.items():
        ahp_result  = get_ahp_weights(name)
        ahp_weights, cr = ahp_result if ahp_result else (None, None)
        profiles_out.append({
            "name":              name,
            "description":       data["description"],
            "manual_weights":    data["weights"],
            "ahp_weights":       ahp_weights,
            "consistency_ratio": cr,
        })
    return {
        "total":    len(PROFILES),
        "profiles": profiles_out,
    }


# ─────────────────────────────────────────
# RECOMMEND
# ─────────────────────────────────────────

@app.get("/recommend")
def get_recommendation(
    profile:    str  = Query(...,           description="Enterprise profile name"),
    commercial: bool = Query(False,         description="Exclude non-commercial licenses"),
    top_n:      int  = Query(3,             description="Number of models to return"),
    method:     str  = Query("ahp_topsis",  description="Scoring method: topsis or ahp_topsis"),
):
    """
    AHP+TOPSIS recommendation endpoint.

    Examples:
        /recommend?profile=coding&commercial=true
        /recommend?profile=coding&method=topsis
        /recommend?profile=rag_long_context&commercial=false&top_n=5
    """
    if profile not in list_profiles():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown profile '{profile}'. Available: {list_profiles()}"
        )

    if method not in ["topsis", "ahp_topsis"]:
        raise HTTPException(
            status_code=400,
            detail="Method must be 'topsis' or 'ahp_topsis'."
        )

    result = recommend(
        profile,
        commercial=commercial,
        top_n=top_n,
        method=method,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.get("/recommend/all")
def get_all_recommendations(
    commercial: bool = Query(False,        description="Exclude non-commercial licenses"),
    method:     str  = Query("ahp_topsis", description="Scoring method: topsis or ahp_topsis"),
):
    """Run recommendation for all profiles at once."""
    results = {}
    for profile_name in list_profiles():
        results[profile_name] = recommend(
            profile_name,
            commercial=commercial,
            top_n=3,
            method=method,
        )
    return results


# ─────────────────────────────────────────
# COLLECTION TRIGGER
# ─────────────────────────────────────────

@app.post("/collect")
def trigger_collection():
    """
    Trigger a full data collection and normalization run.
    Runs HuggingFace + Artificial Analysis + LLM Stats collectors,
    then re-normalizes all metrics.
    """
    from collectors.huggingface         import collect as hf_collect
    from collectors.artificial_analysis import collect as aa_collect
    from collectors.llmstats            import collect as ls_collect
    from collectors.normalizer          import normalize_all

    results = {}

    try:
        hf_collect()
        results["huggingface"] = "ok"
    except Exception as e:
        results["huggingface"] = f"error: {e}"

    try:
        aa_collect()
        results["artificial_analysis"] = "ok"
    except Exception as e:
        results["artificial_analysis"] = f"error: {e}"

    try:
        ls_collect()
        results["llm_stats"] = "ok"
    except Exception as e:
        results["llm_stats"] = f"error: {e}"

    try:
        normalize_all()
        results["normalization"] = "ok"
    except Exception as e:
        results["normalization"] = f"error: {e}"

    return {
        "status":  "collection complete",
        "results": results,
    }


# ─────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────

@app.get("/report/generate")
def generate_report():
    """
    Auto-generate a digest report from the database.
    Returns the report as a JSON response and saves it to disk.
    """
    from reports.generator import generate
    try:
        path = generate()
        return {
            "status":  "ok",
            "message": "Report generated successfully.",
            "path":    path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────

def serialize_model(m: LLMModel) -> dict:
    """Convert a LLMModel DB object to a plain dict for JSON response."""
    return {
        "name":               m.name,
        "provider":           m.provider,
        "source":             m.source,
        "license_type":       m.license_type,
        "intelligence_score": m.intelligence_score,
        "price_input":        m.price_input,
        "price_output":       m.price_output,
        "speed_tps":          m.speed_tps,
        "ttft_ms":            m.ttft_ms,
        "context_window":     m.context_window,
        "norm_intelligence":  m.norm_intelligence,
        "norm_price":         m.norm_price,
        "norm_speed":         m.norm_speed,
        "norm_ttft":          m.norm_ttft,
        "norm_context":       m.norm_context,
        "is_new":             m.is_new,
        "collected_at":       m.collected_at.isoformat() if m.collected_at else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)