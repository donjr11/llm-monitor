# scoring/profiles.py
# Enterprise profiles with scoring weights.
# Weights are used in the TOPSIS weighted matrix (Step 2).
# All weights in each profile must sum to 1.0.

PROFILES = {

    "coding": {
        "description": (
            "Optimized for software development tasks: code generation, "
            "debugging, and code review. Prioritizes intelligence and speed "
            "since developers iterate quickly and need accurate outputs fast."
        ),
        "weights": {
            "norm_intelligence": 0.35,
            "norm_speed":        0.25,
            "norm_price":        0.20,
            "norm_context":      0.10,
            "norm_ttft":         0.10,
        },
    },

    "reasoning": {
        "description": (
            "Optimized for complex analytical tasks: legal analysis, "
            "financial modeling, research synthesis. Heavily weights "
            "intelligence since output quality is non-negotiable."
        ),
        "weights": {
            "norm_intelligence": 0.50,
            "norm_ttft":         0.20,
            "norm_price":        0.15,
            "norm_speed":        0.10,
            "norm_context":      0.05,
        },
    },

    "rag_long_context": {
        "description": (
            "Optimized for Retrieval-Augmented Generation over large document "
            "sets. Context window is the primary constraint — a model that "
            "cannot fit the retrieved chunks is useless regardless of quality."
        ),
        "weights": {
            "norm_context":      0.40,
            "norm_intelligence": 0.25,
            "norm_price":        0.20,
            "norm_speed":        0.10,
            "norm_ttft":         0.05,
        },
    },

    "minimum_cost": {
        "description": (
            "Optimized for high-volume, cost-sensitive workloads: content "
            "moderation, classification, summarization at scale. Price is "
            "the dominant factor while maintaining acceptable quality."
        ),
        "weights": {
            "norm_price":        0.55,
            "norm_speed":        0.20,
            "norm_intelligence": 0.15,
            "norm_ttft":         0.10,
            "norm_context":      0.00,
        },
    },

    "enterprise_agents": {
        "description": (
            "Optimized for autonomous agent pipelines: multi-step reasoning, "
            "tool use, and long-horizon task completion. Balances intelligence "
            "with low latency since agents make many sequential API calls."
        ),
        "weights": {
            "norm_intelligence": 0.40,
            "norm_ttft":         0.25,
            "norm_speed":        0.20,
            "norm_price":        0.10,
            "norm_context":      0.05,
        },
    },

}


def get_profile(name: str) -> dict | None:
    """Return profile config by name, or None if not found."""
    return PROFILES.get(name.lower())


def list_profiles() -> list[str]:
    """Return all available profile names."""
    return list(PROFILES.keys())