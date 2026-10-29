"""
Source-document preview for the evidence drawer (GET /cases/{id}/files/{file_id}/view).

The raw upload is streamed back inline so the browser can render it (PDF at `#page=N`,
TXT/MD as text). Password-protected uploads stay encrypted at rest and their passwords
are never stored, so they can't be previewed: the API answers 423 and the UI falls back
to the verbatim excerpt.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.v1.cases import ALL_ROLES, CONTENT_TYPES, _lock_case
from app.core.auth import CurrentUser, require_roles
from app.core.db import rls_transaction
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/cases", tags=["files"])

# Types a browser can render inline. Text is served as text/plain (never HTML) so an
# uploaded .md can't execute anything; other types are offered as a download.
_INLINE_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "md": "text/plain; charset=utf-8",
}


@router.get("/{case_id}/files/{file_id}/view")
def view_file(
    case_id: str, file_id: str, user: CurrentUser = Depends(require_roles(*ALL_ROLES))
) -> Response:
    with rls_transaction(user.rls) as conn:
        _lock_case(conn, case_id, lock=False)
        try:
            file = conn.execute(
                "select original_filename, file_extension, storage_path, is_encrypted"
                " from case_files where id = %s::uuid and case_id = %s",
                (file_id, case_id),
            ).fetchone()
        except Exception:  # malformed uuid
            file = None
    if file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    if file["is_encrypted"]:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            {"code": "encrypted_at_rest",
             "message": "Password-protected files can't be previewed; passwords aren't stored."},
        )  # fmt: skip

    data = get_storage_provider().get_raw_input_stream(file["storage_path"]).getvalue()
    ext = file["file_extension"]
    inline = ext in _INLINE_TYPES
    media_type = _INLINE_TYPES.get(ext) or CONTENT_TYPES.get(ext, "application/octet-stream")
    name = file["original_filename"].replace('"', "")
    return Response(
        data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
