from sqlalchemy import (
    create_engine, Column, Integer, Float,
    String, Boolean, DateTime, text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
from config import DB_PATH

# Create engine
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# Base class for all models
Base = declarative_base()

# Session factory
SessionLocal = sessionmaker(bind=engine)


class LLMModel(Base):
    """Stores one row per LLM model collected."""
    __tablename__ = "models"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    name            = Column(String, unique=True, nullable=False)
    provider        = Column(String, nullable=True)

    # Raw metrics (as collected from sources)
    intelligence_score  = Column(Float, nullable=True)  # 0-100
    price_input         = Column(Float, nullable=True)  # $/1M tokens
    price_output        = Column(Float, nullable=True)  # $/1M tokens
    speed_tps           = Column(Float, nullable=True)  # tokens/sec
    ttft_ms             = Column(Float, nullable=True)  # ms
    context_window      = Column(Integer, nullable=True)  # tokens
    license_type        = Column(String, nullable=True)  # apache/mit/proprietary

    # Normalized metrics (0-1 scale, filled after normalization)
    norm_intelligence   = Column(Float, nullable=True)
    norm_price          = Column(Float, nullable=True)  # inverted: lower=better
    norm_speed          = Column(Float, nullable=True)
    norm_ttft           = Column(Float, nullable=True)  # inverted: lower=better
    norm_context        = Column(Float, nullable=True)

    # Metadata
    source          = Column(String, nullable=True)
    collected_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_new          = Column(Boolean, default=True)  # True if first time seen


class ScoringRun(Base):
    """Stores scoring results per profile per run."""
    __tablename__ = "scoring_runs"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    run_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    profile      = Column(String, nullable=False)
    model_name   = Column(String, nullable=False)
    score        = Column(Float, nullable=False)
    rank         = Column(Integer, nullable=False)


class ModelSnapshot(Base):
    """
    Historical snapshot of model metrics taken at each collection run.
    Used to detect significant movements: price drops, score changes,
    new models entering or leaving the leaderboard.
    """
    __tablename__ = "model_snapshots"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    name                = Column(String, nullable=False)
    provider            = Column(String, nullable=True)
    intelligence_score  = Column(Float, nullable=True)
    price_input         = Column(Float, nullable=True)
    price_output        = Column(Float, nullable=True)
    speed_tps           = Column(Float, nullable=True)
    ttft_ms             = Column(Float, nullable=True)
    context_window      = Column(Integer, nullable=True)
    license_type        = Column(String, nullable=True)
    source              = Column(String, nullable=True)


def init_db():
    """Create all tables if they don't exist."""
    import os
    os.makedirs("./data", exist_ok=True)
    Base.metadata.create_all(engine)
    print("✅ Database initialized successfully.")


def get_session():
    """Return a new database session."""
    return SessionLocal()


if __name__ == "__main__":
    init_db()