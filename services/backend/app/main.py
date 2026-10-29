from fastapi import FastAPI

from app.api.v1 import cases

app = FastAPI(title="QuotePulse GMC API")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


app.include_router(cases.router, prefix="/api/v1")
