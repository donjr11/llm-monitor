# scoring/ahp.py
# AHP (Analytic Hierarchy Process) weight derivation.
#
# Instead of manually setting weights, AHP derives them from
# pairwise comparison matrices using the Saaty scale (1-9).
#
# Steps:
#   1. Define pairwise comparison matrix per profile
#   2. Normalize each column (divide by column sum)
#   3. Average each row → this gives the priority vector (weights)
#   4. Calculate Consistency Ratio (CR) to validate the matrix
#      CR < 0.10 means the judgments are consistent enough to trust

import numpy as np

# Saaty Random Consistency Index table
# Used to calculate the Consistency Ratio
RANDOM_INDEX = {
    1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90,
    5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41,
}

# Metric order — must be consistent across all matrices
METRICS = [
    "norm_intelligence",
    "norm_speed",
    "norm_price",
    "norm_context",
    "norm_ttft",
]

# ─────────────────────────────────────────
# PAIRWISE COMPARISON MATRICES
# One per enterprise profile.
# Rows/cols follow METRICS order above.
# Values use Saaty scale: 1=equal, 3=moderate, 5=strong, 7=very strong, 9=extreme
# If A is X times more important than B, then B is 1/X times more important than A.
# ─────────────────────────────────────────

COMPARISON_MATRICES = {

    "coding": [
        # intel  speed  price  context  ttft
        [1,      3,     5,     7,       5],   # intelligence
        [1/3,    1,     3,     5,       3],   # speed
        [1/5,    1/3,   1,     3,       1],   # price
        [1/7,    1/5,   1/3,   1,       1/3], # context
        [1/5,    1/3,   1,     3,       1],   # ttft
    ],

    "reasoning": [
        # intel  speed  price  context  ttft
        [1,      5,     7,     9,       3],   # intelligence
        [1/5,    1,     3,     5,       1/3], # speed
        [1/7,    1/3,   1,     3,       1/5], # price
        [1/9,    1/5,   1/3,   1,       1/7], # context
        [1/3,    3,     5,     7,       1],   # ttft
    ],

    "rag_long_context": [
        # intel  speed  price  context  ttft
        [1,      3,     1,     1/3,     5],   # intelligence
        [1/3,    1,     1/3,   1/7,     3],   # speed
        [1,      3,     1,     1/3,     5],   # price
        [3,      7,     3,     1,       9],   # context
        [1/5,    1/3,   1/5,   1/9,     1],   # ttft
    ],

    "minimum_cost": [
        # intel  speed  price  context  ttft
        [1,      1/3,   1/5,   3,       1/3], # intelligence
        [3,      1,     1/3,   5,       1],   # speed
        [5,      3,     1,     7,       3],   # price
        [1/3,    1/5,   1/7,   1,       1/5], # context
        [3,      1,     1/3,   5,       1],   # ttft
    ],

    "enterprise_agents": [
        # intel  speed  price  context  ttft
        [1,      3,     5,     7,       1/3], # intelligence
        [1/3,    1,     3,     5,       1/5], # speed
        [1/5,    1/3,   1,     3,       1/7], # price
        [1/7,    1/5,   1/3,   1,       1/9], # context
        [3,      5,     7,     9,       1],   # ttft
    ],
}


def derive_weights(matrix: list[list[float]]) -> tuple[dict, float]:
    """
    Derive AHP weights from a pairwise comparison matrix.

    Steps:
      1. Normalize columns (divide each value by column sum)
      2. Average each row → priority vector (weights)
      3. Compute lambda_max → CI → CR

    Returns:
      weights : dict mapping metric name to weight
      cr      : Consistency Ratio (should be < 0.10)
    """
    A = np.array(matrix, dtype=float)
    n = A.shape[0]

    # Step 1 — normalize columns
    col_sums = A.sum(axis=0)
    normalized = A / col_sums

    # Step 2 — row averages = priority vector
    priority_vector = normalized.mean(axis=1)

    # Step 3 — consistency check
    weighted_sum = A @ priority_vector
    lambda_max   = (weighted_sum / priority_vector).mean()
    ci           = (lambda_max - n) / (n - 1)
    ri           = RANDOM_INDEX.get(n, 1.12)
    cr           = ci / ri if ri > 0 else 0.0

    # Build weights dict
    weights = {
        metric: round(float(priority_vector[i]), 6)
        for i, metric in enumerate(METRICS)
    }

    return weights, round(cr, 4)


def get_ahp_weights(profile_name: str) -> tuple[dict, float] | None:
    """
    Get AHP-derived weights for a given profile.
    Returns (weights_dict, consistency_ratio) or None if profile not found.
    """
    matrix = COMPARISON_MATRICES.get(profile_name)
    if matrix is None:
        return None
    return derive_weights(matrix)


def validate_all_profiles() -> dict:
    """
    Validate all profile matrices and return CR for each.
    CR < 0.10 is acceptable. CR >= 0.10 means matrix needs adjustment.
    """
    results = {}
    for profile_name, matrix in COMPARISON_MATRICES.items():
        weights, cr = derive_weights(matrix)
        status = "✅ consistent" if cr < 0.10 else "⚠️  inconsistent (CR >= 0.10)"
        results[profile_name] = {
            "weights": weights,
            "cr":      cr,
            "status":  status,
        }
    return results


if __name__ == "__main__":
    print("🧮 AHP Weight Derivation — All Profiles\n")
    results = validate_all_profiles()
    for profile, data in results.items():
        print(f"Profile: {profile}")
        print(f"  CR = {data['cr']} {data['status']}")
        print(f"  Weights:")
        for metric, w in data["weights"].items():
            label = metric.replace("norm_", "")
            print(f"    {label:<15} {w:.4f}")
        print()