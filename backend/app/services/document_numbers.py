from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.enums import DocumentPrefix
from app.models.return_void import DocumentNumberSequence


def mint_document_number(
    db: Session,
    prefix: DocumentPrefix,
    branch_id: UUID,
) -> str:
    year = datetime.now(timezone.utc).year
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise ValueError("Branch not found for document number")

    seq = db.scalar(
        select(DocumentNumberSequence)
        .where(
            DocumentNumberSequence.branch_id == branch_id,
            DocumentNumberSequence.prefix == prefix,
            DocumentNumberSequence.year == year,
        )
        .with_for_update()
    )
    if seq is None:
        seq = DocumentNumberSequence(
            branch_id=branch_id,
            prefix=prefix,
            year=year,
            last_value=0,
        )
        db.add(seq)
        db.flush()
    seq.last_value += 1
    db.flush()
    return f"{prefix.value}-{branch.code}-{year}-{seq.last_value:05d}"
