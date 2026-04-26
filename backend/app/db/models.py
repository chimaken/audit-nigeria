from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ElectionType(str, enum.Enum):
    NATIONAL = "National"
    STATE = "State"
    LGA = "LGA"


class ConsensusStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"


class Election(Base):
    __tablename__ = "elections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ElectionType] = mapped_column(
        SQLEnum(
            ElectionType,
            native_enum=False,
            length=32,
            values_callable=lambda t: [m.value for m in t],
        ),
        nullable=False,
    )

    result_clusters: Mapped[list["ResultCluster"]] = relationship(
        back_populates="election", cascade="all, delete-orphan"
    )
    national_tally: Mapped[Optional["NationalResultTally"]] = relationship(
        back_populates="election", uselist=False, cascade="all, delete-orphan"
    )
    state_tallies: Mapped[list["StateResultTally"]] = relationship(
        back_populates="election", cascade="all, delete-orphan"
    )
    lga_tallies: Mapped[list["LgaResultTally"]] = relationship(
        back_populates="election", cascade="all, delete-orphan"
    )


class State(Base):
    __tablename__ = "states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    lgas: Mapped[list["LGA"]] = relationship(back_populates="state")


class LGA(Base):
    __tablename__ = "lgas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id"), nullable=False)

    state: Mapped["State"] = relationship(back_populates="lgas")
    polling_units: Mapped[list["PollingUnit"]] = relationship(back_populates="lga")

    __table_args__ = (UniqueConstraint("name", "state_id", name="uq_lga_name_state"),)


class PollingUnit(Base):
    __tablename__ = "polling_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ward: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lga_id: Mapped[int] = mapped_column(ForeignKey("lgas.id"), nullable=False)
    pu_code: Mapped[str] = mapped_column(String(64), nullable=False)

    lga: Mapped["LGA"] = relationship(back_populates="polling_units")
    result_clusters: Mapped[list["ResultCluster"]] = relationship(
        back_populates="polling_unit"
    )

    __table_args__ = (UniqueConstraint("pu_code", name="uq_pu_code"),)


class ResultCluster(Base):
    __tablename__ = "result_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pu_id: Mapped[int] = mapped_column(ForeignKey("polling_units.id"), nullable=False)
    election_id: Mapped[int] = mapped_column(ForeignKey("elections.id"), nullable=False)
    current_consensus_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    party_results: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    consensus_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ConsensusStatus.PENDING.value,
        server_default="PENDING",
    )

    polling_unit: Mapped["PollingUnit"] = relationship(back_populates="result_clusters")
    election: Mapped["Election"] = relationship(back_populates="result_clusters")
    uploads: Mapped[list["Upload"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("result_clusters.id"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    phash: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_blurry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="received")
    blur_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)

    cluster: Mapped["ResultCluster"] = relationship(back_populates="uploads")


class UploadAsyncJob(Base):
    """S3 staging + SQS + Lambda pipeline for long-running uploads (see /upload/async/*)."""

    __tablename__ = "upload_async_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    election_id: Mapped[int] = mapped_column(ForeignKey("elections.id"), nullable=False)
    pu_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    staging_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    election: Mapped["Election"] = relationship()


class NationalResultTally(Base):
    """Aggregated national party totals for an election (JSONB)."""

    __tablename__ = "national_result_tallies"

    election_id: Mapped[int] = mapped_column(
        ForeignKey("elections.id", ondelete="CASCADE"), primary_key=True
    )
    party_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    election: Mapped[Election] = relationship(back_populates="national_tally")


class StateResultTally(Base):
    __tablename__ = "state_result_tallies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    election_id: Mapped[int] = mapped_column(
        ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state_id: Mapped[int] = mapped_column(
        ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    party_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    election: Mapped[Election] = relationship(back_populates="state_tallies")

    __table_args__ = (
        UniqueConstraint("election_id", "state_id", name="uq_state_tally_election_state"),
    )


class LgaResultTally(Base):
    __tablename__ = "lga_result_tallies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    election_id: Mapped[int] = mapped_column(
        ForeignKey("elections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lga_id: Mapped[int] = mapped_column(
        ForeignKey("lgas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    party_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    election: Mapped[Election] = relationship(back_populates="lga_tallies")

    __table_args__ = (
        UniqueConstraint("election_id", "lga_id", name="uq_lga_tally_election_lga"),
    )
