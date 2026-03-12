# Purpose: Define the Supplier and SupplierYearData ORM models used by the application.
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Supplier(Base):
    """A supplier entity that can have many yearly financial records."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    yearly_data: Mapped[list["SupplierYearData"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        order_by="SupplierYearData.year",
    )


class SupplierYearData(Base):
    """Financial data for one supplier in one reporting year."""

    __tablename__ = "supplier_year_data"
    __table_args__ = (UniqueConstraint("supplier_id", "year", name="uq_supplier_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)

    turnover: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ebit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    employees: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    investments: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quick_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    equity_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    debt_repayment_period: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_on_total_assets: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cash_flow_performance_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    financial_stability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    earnings_power: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    supplier: Mapped[Supplier] = relationship(back_populates="yearly_data")
