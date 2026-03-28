# app/main.py
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.core.db import engine, init_db
from app.core.models import SQLModel
from app.routers.actions import router as actions_router
from app.routers.cases import router as cases_router
from app.routers.scans import router as scans_router
from app.routers.uploads import router as uploads_router

# ADD:
from app.routers.admin_rules import router as admin_rules_router
from app.triage.rules_seed import seed_triage_rules

app = FastAPI(
    title="GM Full-Size SUV AI Shop System",
    version="1.0.0",
    description="2021+ Suburban / Tahoe / Yukon / Escalade AI shop-grade workflow",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ADD: let routers reuse templates consistently
app.state.templates = templates


@app.on_event("startup")
def _startup() -> None:
    # keep your existing init
    init_db()

    # ADD: create tables for any new models + seed starter rules
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_triage_rules(session)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


app.include_router(cases_router, prefix="/api")
app.include_router(scans_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")

# ADD:
app.include_router(admin_rules_router)
