import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.deps import require_role
from app.models.enums import Role
from app.models.user import User
from app.services.uploads import UPLOAD_DIR

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@router.post("/payment-proof")
async def upload_payment_proof(
    file: UploadFile = File(...),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> dict[str, str]:
    content_type = (file.content_type or "").lower()
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        # Fall back to filename suffix for common image types
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image uploads are allowed",
            )
        ext = ".jpg" if suffix == ".jpeg" else suffix

    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    dest.write_bytes(data)
    return {"url": f"/uploads/payment_proofs/{filename}"}
