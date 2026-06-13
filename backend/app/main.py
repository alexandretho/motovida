from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import models  # noqa: F401  (registra os modelos no metadata)
from .config import SECRET_KEY
from .database import Base, SessionLocal, engine, wait_for_db
from .routers import admin, affiliate, auth, public
from .seeds import run_seeds

app = FastAPI(title="Sistema Nacional de Cadastro e Atendimento – Instituto MotoVida Guilherme França")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 8, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(affiliate.router)
app.include_router(admin.router)


@app.on_event("startup")
def startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_seeds(db)
    finally:
        db.close()
