import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LineageEdge(Base):
    __tablename__ = "lineage_edges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    source_column: Mapped[str] = mapped_column(String(200), nullable=False)
    target_dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    target_column: Mapped[str] = mapped_column(String(200), nullable=False)
    transform_expr: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
