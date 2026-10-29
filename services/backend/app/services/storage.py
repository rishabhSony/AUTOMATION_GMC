"""
Storage providers (TRD §5.1) and zero-persistence decryption (CLAUDE.md invariant 4).

Providers return a storage *key* relative to the storage root
(`inputs/raw/{case_id}/{ts}_{name}`), identical for local and S3, and that key is what
`case_files.storage_path` holds.

Decryption runs entirely on in-memory buffers: decrypted bytes and passwords are never
written to disk or logged, and callers drop references once the stream is consumed.
"""

import abc
import io
import re
import time
from enum import StrEnum
from pathlib import Path

import msoffcrypto
import pymupdf
from msoffcrypto.exceptions import FileFormatError

from app.core.config import get_settings

# Excel's built-in key for "read-only recommended" workbooks; not a user secret.
_EXCEL_DEFAULT_PASSWORD = "VelvetSweatshop"


class PasswordRequiredException(Exception):
    """The file is encrypted and no password was supplied."""

    def __init__(self, filename: str):
        super().__init__(f"'{filename}' is password-protected")
        self.filename = filename


class InvalidPasswordException(Exception):
    """The supplied password does not open the file."""

    def __init__(self, filename: str):
        super().__init__(f"Incorrect password for '{filename}'")
        self.filename = filename


class FileKind(StrEnum):
    PDF = "pdf"
    OFFICE = "office"  # xlsx/xls/docx (OLE or OOXML containers)
    OTHER = "other"


# ---------------------------------------------------------------------------
# Storage providers
# ---------------------------------------------------------------------------


def safe_filename(filename: str) -> str:
    """Strips directories and unsafe characters so a name can't escape its case folder."""
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name[:200] or "upload"


def _raw_key(case_id: str, filename: str) -> str:
    return f"inputs/raw/{case_id}/{int(time.time() * 1000)}_{safe_filename(filename)}"


def _analysis_key(case_id: str, filename: str) -> str:
    return f"outputs/analysis/{case_id}/{safe_filename(filename)}"


class BaseStorageProvider(abc.ABC):
    @abc.abstractmethod
    def save_raw_input(
        self, case_id: str, filename: str, data: bytes, content_type: str
    ) -> str: ...

    @abc.abstractmethod
    def get_raw_input_stream(self, file_key: str) -> io.BytesIO: ...

    @abc.abstractmethod
    def save_analysis_output(
        self, case_id: str, filename: str, data: bytes, content_type: str
    ) -> str: ...


class LocalStorageProvider(BaseStorageProvider):
    """Stage 1: local filesystem under LOCAL_STORAGE_PATH (repo-root `storage/`)."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = (base_dir or get_settings().storage_root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        if not path.is_relative_to(self.base_dir):
            raise ValueError(f"Storage key escapes storage root: {key}")
        return path

    def _write(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def save_raw_input(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        return self._write(_raw_key(case_id, filename), data)

    def get_raw_input_stream(self, file_key: str) -> io.BytesIO:
        return io.BytesIO(self._path(file_key).read_bytes())

    def save_analysis_output(
        self, case_id: str, filename: str, data: bytes, content_type: str
    ) -> str:
        return self._write(_analysis_key(case_id, filename), data)


class S3StorageProvider(BaseStorageProvider):
    """Stage 2: AWS S3 on EC2 (Phase N+2), behind the corporate proxy when configured."""

    def __init__(self):
        import boto3
        from botocore.config import Config

        settings = get_settings()
        self.bucket = settings.GMC_S3_BUCKET_NAME
        proxies = (
            {"http": settings.HTTP_PROXY, "https": settings.HTTPS_PROXY}
            if settings.HTTP_PROXY
            else None
        )
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                proxies=proxies,
            ),
        )

    def _put(self, key: str, data: bytes, content_type: str, case_id: str, stage: str) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
            Metadata={"case_id": case_id, "stage": stage},
        )
        return key

    def save_raw_input(self, case_id: str, filename: str, data: bytes, content_type: str) -> str:
        return self._put(_raw_key(case_id, filename), data, content_type, case_id, "raw_upload")

    def get_raw_input_stream(self, file_key: str) -> io.BytesIO:
        res = self.client.get_object(Bucket=self.bucket, Key=file_key)
        return io.BytesIO(res["Body"].read())

    def save_analysis_output(
        self, case_id: str, filename: str, data: bytes, content_type: str
    ) -> str:
        key = _analysis_key(case_id, filename)
        return self._put(key, data, content_type, case_id, "analyzed_output")


def get_storage_provider() -> BaseStorageProvider:
    if get_settings().STORAGE_BACKEND == "s3":
        return S3StorageProvider()
    return LocalStorageProvider()


# ---------------------------------------------------------------------------
# Encryption inspection & in-memory decryption
# ---------------------------------------------------------------------------


def detect_kind(data: bytes) -> FileKind:
    if data[:5] == b"%PDF-":
        return FileKind.PDF
    # OLE2 compound file (xls/doc, and encrypted xlsx/docx) or ZIP (xlsx/docx)
    if data[:8] == bytes.fromhex("D0CF11E0A1B11AE1") or data[:4] == b"PK\x03\x04":
        return FileKind.OFFICE
    return FileKind.OTHER


def _office_file(data: bytes):
    try:
        return msoffcrypto.OfficeFile(io.BytesIO(data))
    except FileFormatError:
        return None  # not an Office container msoffcrypto understands → treat as plain


def _office_decrypt(office, password: str) -> io.BytesIO:
    out = io.BytesIO()
    office.load_key(password=password)
    office.decrypt(out)
    out.seek(0)
    return out


def is_password_protected(data: bytes) -> bool:
    """True when opening the file needs a user-supplied password."""
    kind = detect_kind(data)
    if kind is FileKind.PDF:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return bool(doc.needs_pass)
    if kind is FileKind.OFFICE:
        office = _office_file(data)
        if office is None or not office.is_encrypted():
            return False
        try:
            _office_decrypt(office, _EXCEL_DEFAULT_PASSWORD)
            return False
        except Exception:
            return True
    return False


def open_decrypted(data: bytes, filename: str, password: str | None = None) -> io.BytesIO:
    """
    Returns a readable in-memory stream of the file's plaintext.

    Raises PasswordRequiredException when the file is protected and no password is
    given, and InvalidPasswordException when the password is wrong. Unprotected
    files are returned as-is.
    """
    kind = detect_kind(data)

    if kind is FileKind.PDF:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if not doc.needs_pass:
                return io.BytesIO(data)
            if not password:
                raise PasswordRequiredException(filename)
            if not doc.authenticate(password):
                raise InvalidPasswordException(filename)
            return io.BytesIO(doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_NONE))

    if kind is FileKind.OFFICE:
        office = _office_file(data)
        if office is None or not office.is_encrypted():
            return io.BytesIO(data)
        try:
            return _office_decrypt(office, _EXCEL_DEFAULT_PASSWORD)
        except Exception:
            pass
        if not password:
            raise PasswordRequiredException(filename)
        try:
            return _office_decrypt(office, password)
        except Exception as exc:  # InvalidKeyError, or corrupt key material
            raise InvalidPasswordException(filename) from exc

    return io.BytesIO(data)
