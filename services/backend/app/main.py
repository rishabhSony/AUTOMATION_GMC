from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import cases, exports, workbench
from app.core.config import get_settings

app = FastAPI(title="QuotePulse GMC API")

# The Next.js workbench calls the API from the browser with a Clerk Bearer token.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().CORS_ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


app.include_router(cases.router, prefix="/api/v1")
app.include_router(workbench.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
