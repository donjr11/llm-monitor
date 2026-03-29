from database import get_session, LLMModel


def min_max_normalize(value, min_val, max_val):
    """Scale a value to 0-1 range. Returns 0.5 if range is zero."""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


def normalize_all():
    """
    Normalize all raw metrics across all models to 0-1 scale.
    - Higher is better: intelligence, speed, context_window
    - Lower is better: price, ttft (so we invert them)
    """
    session = get_session()
    models = session.query(LLMModel).all()

    if not models:
        print("❌ No models found in database.")
        session.close()
        return

    # --- Collect all raw values ---
    intelligence_vals = [m.intelligence_score for m in models if m.intelligence_score is not None]
    speed_vals        = [m.speed_tps          for m in models if m.speed_tps          is not None]
    ttft_vals         = [m.ttft_ms            for m in models if m.ttft_ms            is not None]
    context_vals      = [m.context_window     for m in models if m.context_window     is not None]

    # For price we use average of input+output per model
    price_vals = []
    for m in models:
        if m.price_input is not None and m.price_output is not None:
            price_vals.append((m.price_input + m.price_output) / 2)

    # --- Compute min/max for each metric ---
    def safe_min(lst): return min(lst) if lst else 0
    def safe_max(lst): return max(lst) if lst else 1

    min_intel   = safe_min(intelligence_vals)
    max_intel   = safe_max(intelligence_vals)
    min_speed   = safe_min(speed_vals)
    max_speed   = safe_max(speed_vals)
    min_ttft    = safe_min(ttft_vals)
    max_ttft    = safe_max(ttft_vals)
    min_context = safe_min(context_vals)
    max_context = safe_max(context_vals)
    min_price   = safe_min(price_vals)
    max_price   = safe_max(price_vals)

    # --- Normalize and save ---
    updated = 0
    for m in models:
        # Intelligence: higher = better
        if m.intelligence_score is not None:
            m.norm_intelligence = round(min_max_normalize(
                m.intelligence_score, min_intel, max_intel), 4)

        # Speed: higher = better
        if m.speed_tps is not None:
            m.norm_speed = round(min_max_normalize(
                m.speed_tps, min_speed, max_speed), 4)

        # TTFT: lower = better → invert
        if m.ttft_ms is not None:
            raw = min_max_normalize(m.ttft_ms, min_ttft, max_ttft)
            m.norm_ttft = round(1 - raw, 4)

        # Context window: higher = better
        if m.context_window is not None:
            m.norm_context = round(min_max_normalize(
                m.context_window, min_context, max_context), 4)

        # Price: lower = better → invert
        if m.price_input is not None and m.price_output is not None:
            avg_price = (m.price_input + m.price_output) / 2
            raw = min_max_normalize(avg_price, min_price, max_price)
            m.norm_price = round(1 - raw, 4)

        updated += 1

    session.commit()
    session.close()

    print(f"✅ Normalization complete — {updated} models normalized.")
    print(f"   Intelligence range : {min_intel:.1f} → {max_intel:.1f}")
    print(f"   Speed range        : {min_speed:.1f} → {max_speed:.1f} tokens/s")
    print(f"   TTFT range         : {min_ttft:.0f} → {max_ttft:.0f} ms")
    print(f"   Context range      : {min_context:,} → {max_context:,} tokens")
    print(f"   Price range        : ${min_price:.3f} → ${max_price:.3f} /1M tokens")


if __name__ == "__main__":
    normalize_all()