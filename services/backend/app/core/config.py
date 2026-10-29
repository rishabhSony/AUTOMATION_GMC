from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env.backend.local", extra="ignore")

    ENVIRONMENT: str = "development"

    # Storage (TRD §12)
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "../../storage"  # relative to services/backend
    GMC_S3_BUCKET_NAME: str = ""
    AWS_REGION: str = "ap-south-1"
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""

    DATABASE_URL: str = ""

    # Clerk session JWT verification (Doc 05 §8: Clerk Bearer JWT on every endpoint)
    CLERK_JWKS_URL: str = ""
    CLERK_ISSUER: str = ""
    CLERK_AUTHORIZED_PARTIES: str = "http://localhost:3000"
    # Browser origins allowed to call the API (comma-separated)
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

    # AI inference (TRD §12)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_EXTRACTION: str = "gpt-5.4-mini"
    OPENAI_MODEL_VERIFICATION: str = "gpt-5.4-mini"
    OPENAI_ZERO_DATA_RETENTION: bool = True
    OPENAI_TIMEOUT_SECONDS: float = 60
    OPENAI_MAX_RETRIES: int = 3

    # RFQ parsing: "pymupdf" (default; Docling only for scanned PDFs) or "docling"
    PARSER_PDF_ENGINE: str = "pymupdf"

    @property
    def storage_root(self) -> Path:
        root = Path(self.LOCAL_STORAGE_PATH)
        return root if root.is_absolute() else (BACKEND_DIR / root).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
