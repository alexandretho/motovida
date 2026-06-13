import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_db(retries: int = 30, delay: float = 2.0):
    """Aguarda o MySQL ficar disponível antes de criar as tabelas."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[motovida] Banco de dados disponível.")
            return
        except Exception as exc:
            print(f"[motovida] Aguardando MySQL ({attempt}/{retries})... {exc}")
            time.sleep(delay)
    raise RuntimeError("Não foi possível conectar ao MySQL.")
