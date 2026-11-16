from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.seeds import run_seeds


def test_default_seed_creates_admin_without_fictional_records(monkeypatch):
    monkeypatch.delenv("SEED_SAMPLE_DATA", raising=False)
    engine = create_engine("sqlite://")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        run_seeds(db)
        assert db.query(models.User).count() == 1
        assert db.query(models.User).filter_by(role="admin").count() == 1
        assert db.query(models.Affiliate).count() == 0
        assert db.query(models.Course).count() == 0
        assert db.query(models.Partner).count() == 0
        assert db.query(models.Event).count() == 0
    engine.dispose()


def test_explicit_sample_seed_adds_fictional_demo_data(monkeypatch):
    monkeypatch.setenv("SEED_SAMPLE_DATA", "1")
    engine = create_engine("sqlite://")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        run_seeds(db)
        assert db.query(models.User).count() == 2
        assert db.query(models.Affiliate).count() == 1
        assert db.query(models.Course).count() == 5
        assert db.query(models.Partner).count() == 8
        assert db.query(models.Event).count() == 1
    engine.dispose()
