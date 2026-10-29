"""Reference lookups used before a case exists (e.g. the /cases/new Zone indicator)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.cases import ALL_ROLES
from app.core.auth import CurrentUser, require_roles
from app.core.db import rls_transaction
from app.services import derivations

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/zone")
def resolve_zone(
    pincode: Annotated[str | None, Query(pattern=r"^[1-9][0-9]{5}$")] = None,
    state: Annotated[str | None, Query(max_length=100)] = None,
    district: Annotated[str | None, Query(max_length=100)] = None,
    user: CurrentUser = Depends(require_roles(*ALL_ROLES)),
) -> dict:
    """Same lookup as PATCH /manual-inputs: zone_master by PIN, then State + District."""
    with rls_transaction(user.rls) as conn:
        zone, matched_by = derivations.resolve_zone(conn, pincode, state, district)
    return {"zone": zone, "matched_by": matched_by}
