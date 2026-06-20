from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.routers import admin, auth_router, internal, readings, setpoints, terminal


def run_migrations():
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    if "command_logs" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("command_logs")}
        with engine.begin() as conn:
            if "triggered_by" not in cols:
                conn.execute(text("ALTER TABLE command_logs ADD COLUMN triggered_by VARCHAR(50)"))
            if "source" not in cols:
                conn.execute(text("ALTER TABLE command_logs ADD COLUMN source VARCHAR(50)"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Gasificado API", version="1.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(readings.router)
app.include_router(setpoints.router)
app.include_router(admin.router)
app.include_router(internal.router)
app.include_router(terminal.router)


@app.get("/health")
def health():
    return {"status": "ok", "timezone": "America/Bogota"}
