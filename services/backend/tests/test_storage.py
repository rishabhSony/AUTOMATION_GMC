import io

import openpyxl
import pymupdf
import pytest
from msoffcrypto.format.ooxml import OOXMLFile

from app.services.storage import (
    InvalidPasswordException,
    LocalStorageProvider,
    PasswordRequiredException,
    is_password_protected,
    open_decrypted,
    safe_filename,
)


def xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    wb.active.append(["Emp ID", "Relation", "DOB"])
    wb.active.append(["E1", "Self", "01-01-1990"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def encrypted_xlsx_bytes(password: str) -> bytes:
    out = io.BytesIO()
    OOXMLFile(io.BytesIO(xlsx_bytes())).encrypt(password, out)
    return out.getvalue()


def pdf_bytes(user_pw: str | None = None) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "RFQ")
    if user_pw is None:
        return doc.tobytes()
    return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=user_pw, owner_pw="o")


@pytest.mark.parametrize(
    ("data", "protected"),
    [
        (xlsx_bytes(), False),
        (encrypted_xlsx_bytes("s3cret"), True),
        (pdf_bytes(), False),
        (pdf_bytes("s3cret"), True),
        (b"Emp ID,Relation\nE1,Self\n", False),
    ],
)
def test_is_password_protected(data, protected):
    assert is_password_protected(data) is protected


@pytest.mark.parametrize("make", [encrypted_xlsx_bytes, pdf_bytes])
def test_password_required_and_invalid(make):
    data = make("s3cret")
    with pytest.raises(PasswordRequiredException):
        open_decrypted(data, "file")
    with pytest.raises(InvalidPasswordException):
        open_decrypted(data, "file", "wrong")


def test_decrypts_xlsx_in_memory():
    stream = open_decrypted(encrypted_xlsx_bytes("s3cret"), "census.xlsx", "s3cret")
    assert isinstance(stream, io.BytesIO)
    wb = openpyxl.load_workbook(stream)
    assert wb.active["A2"].value == "E1"


def test_decrypts_pdf_in_memory():
    stream = open_decrypted(pdf_bytes("s3cret"), "rfq.pdf", "s3cret")
    with pymupdf.open(stream=stream.getvalue(), filetype="pdf") as doc:
        assert not doc.needs_pass
        assert "RFQ" in doc[0].get_text()


def test_unprotected_file_passes_through():
    data = xlsx_bytes()
    assert open_decrypted(data, "census.xlsx").getvalue() == data


@pytest.mark.parametrize(
    ("raw", "safe"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\boot.ini", "boot.ini"),
        ("Apex Census (Locked).xlsx", "Apex Census _Locked_.xlsx"),
        ("..", "upload"),
    ],
)
def test_safe_filename(raw, safe):
    assert safe_filename(raw) == safe


def test_local_provider_paths(tmp_path):
    storage = LocalStorageProvider(base_dir=tmp_path)
    key = storage.save_raw_input("case-1", "../census.xlsx", b"data", "application/x")
    assert key.startswith("inputs/raw/case-1/") and key.endswith("_census.xlsx")
    assert (tmp_path / key).read_bytes() == b"data"
    assert storage.get_raw_input_stream(key).getvalue() == b"data"

    out = storage.save_analysis_output("case-1", "report.xlsx", b"x", "application/x")
    assert out == "outputs/analysis/case-1/report.xlsx"
    with pytest.raises(ValueError):
        storage.get_raw_input_stream("../../outside")
