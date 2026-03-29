# reports/generator.py
# Auto-generates a markdown digest report from the database.
# Called by the /report/generate API endpoint.

import os
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader
from database import get_session, LLMModel, ModelSnapshot
from scoring.engine import recommend


def take_snapshot(session):
    """
    Save a snapshot of all current model metrics for historical tracking.
    This enables detection of price drops, score changes, etc.
    """
    models = session.query(LLMModel).all()
    now = datetime.now(timezone.utc)
    for m in models:
        session.add(ModelSnapshot(
            snapshot_at=now,
            name=m.name,
            provider=m.provider,
            intelligence_score=m.intelligence_score,
            price_input=m.price_input,
            price_output=m.price_output,
            speed_tps=m.speed_tps,
            ttft_ms=m.ttft_ms,
            context_window=m.context_window,
            license_type=m.license_type,
            source=m.source,
        ))
    session.commit()


def detect_movements(session) -> list[dict]:
    """
    Compare current model metrics against the most recent previous snapshot
    to detect significant movements: price drops/increases, score changes,
    new models, and removed models.

    Returns a list of movement dicts with keys: model, type, detail.
    """
    from sqlalchemy import func, distinct

    movements = []

    # Find the two most recent distinct snapshot timestamps
    snapshot_times = (
        session.query(distinct(ModelSnapshot.snapshot_at))
        .order_by(ModelSnapshot.snapshot_at.desc())
        .limit(2)
        .all()
    )
    snapshot_times = [row[0] for row in snapshot_times]

    if len(snapshot_times) < 2:
        # No previous snapshot to compare against
        return movements

    current_time = snapshot_times[0]
    previous_time = snapshot_times[1]

    current_snaps = {
        s.name: s for s in
        session.query(ModelSnapshot).filter(
            ModelSnapshot.snapshot_at == current_time
        ).all()
    }
    previous_snaps = {
        s.name: s for s in
        session.query(ModelSnapshot).filter(
            ModelSnapshot.snapshot_at == previous_time
        ).all()
    }

    # Detect new models (in current but not in previous)
    for name in current_snaps:
        if name not in previous_snaps:
            movements.append({
                "model": name,
                "type": "New Model",
                "detail": f"{name} appeared for the first time",
            })

    # Detect removed models
    for name in previous_snaps:
        if name not in current_snaps:
            movements.append({
                "model": name,
                "type": "Removed",
                "detail": f"{name} is no longer tracked",
            })

    # Detect price and score changes for models present in both
    for name in current_snaps:
        if name not in previous_snaps:
            continue
        curr = current_snaps[name]
        prev = previous_snaps[name]

        # Price drop/increase (input price, threshold: 10%)
        if curr.price_input is not None and prev.price_input is not None and prev.price_input > 0:
            pct = (curr.price_input - prev.price_input) / prev.price_input * 100
            if pct <= -10:
                movements.append({
                    "model": name,
                    "type": "Price Drop",
                    "detail": (
                        f"Input price dropped {abs(pct):.0f}%: "
                        f"${prev.price_input:.3f} -> ${curr.price_input:.3f}/1M tokens"
                    ),
                })
            elif pct >= 10:
                movements.append({
                    "model": name,
                    "type": "Price Increase",
                    "detail": (
                        f"Input price increased {pct:.0f}%: "
                        f"${prev.price_input:.3f} -> ${curr.price_input:.3f}/1M tokens"
                    ),
                })

        # Score change (threshold: 2 points)
        if curr.intelligence_score is not None and prev.intelligence_score is not None:
            diff = curr.intelligence_score - prev.intelligence_score
            if abs(diff) >= 2.0:
                direction = "improved" if diff > 0 else "declined"
                movements.append({
                    "model": name,
                    "type": f"Score {'Up' if diff > 0 else 'Down'}",
                    "detail": (
                        f"Intelligence score {direction} by {abs(diff):.1f}: "
                        f"{prev.intelligence_score:.1f} -> {curr.intelligence_score:.1f}"
                    ),
                })

        # Speed improvement (threshold: 15%)
        if curr.speed_tps is not None and prev.speed_tps is not None and prev.speed_tps > 0:
            pct = (curr.speed_tps - prev.speed_tps) / prev.speed_tps * 100
            if pct >= 15:
                movements.append({
                    "model": name,
                    "type": "Speed Up",
                    "detail": (
                        f"Speed improved {pct:.0f}%: "
                        f"{prev.speed_tps:.0f} -> {curr.speed_tps:.0f} tok/s"
                    ),
                })

    return movements


def generate() -> str:
    """
    Generate a markdown digest report from current DB state.
    Returns the path to the generated file.
    """
    session = get_session()

    # --- Take a snapshot for historical tracking ---
    take_snapshot(session)

    # --- Collect data ---
    all_models = session.query(LLMModel).all()
    new_models = session.query(LLMModel).filter(LLMModel.is_new == True).all()

    # Count by source
    sources = {}
    for m in all_models:
        sources[m.source or "unknown"] = sources.get(m.source or "unknown", 0) + 1
    sources_str = ", ".join(f"{k} ({v})" for k, v in sources.items())

    # --- Detect significant movements ---
    movements = detect_movements(session)

    session.close()

    # --- Score all profiles (top 5 per spec) ---
    profiles = {}
    profile_names = ["coding", "reasoning", "rag_long_context",
                     "minimum_cost", "enterprise_agents"]
    for name in profile_names:
        result = recommend(name, commercial=False, top_n=5)
        if "error" not in result:
            profiles[name] = result

    # --- Top 10 by reasoning profile ---
    reasoning = profiles.get("reasoning", {})
    top10_reasoning = []
    for item in reasoning.get("all_scored", [])[:10]:
        top10_reasoning.append({
            "name":          item["name"],
            "provider":      item["provider"],
            "intelligence":  item["intelligence"],
            "price_input":   item["price_input"],
            "speed_tps":     item["speed_tps"],
            "context_window": item["context_window"],
        })

    # --- Render template ---
    template_dir = os.path.join(os.path.dirname(__file__))
    env      = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("template.md")

    rendered = template.render(
        generated_at    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total_models    = len(all_models),
        sources         = sources_str,
        new_models      = [serialize(m) for m in new_models],
        movements       = movements,
        profiles        = profiles,
        top10_reasoning = top10_reasoning,
    )

    # --- Save to disk ---
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = f"reports/digest_{timestamp}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"Report saved to {output_path}")
    return output_path


def serialize(m: LLMModel) -> dict:
    return {
        "name":         m.name,
        "provider":     m.provider,
        "license_type": m.license_type or "unknown",
        "source":       m.source or "unknown",
    }


if __name__ == "__main__":
    path = generate()
    print(f"Report generated: {path}")
