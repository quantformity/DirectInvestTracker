from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Float, DateTime, Date, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class CategoryEnum(str, enum.Enum):
    Equity = "Equity"
    GIC = "GIC"
    Cash = "Cash"
    Dividend = "Dividend"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CAD")

    positions: Mapped[list["Position"]] = relationship("Position", back_populates="account", cascade="all, delete-orphan")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(SAEnum(CategoryEnum), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    cost_per_share: Mapped[float] = mapped_column(Float, nullable=False)
    date_added: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    yield_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD", server_default="USD")

    account: Mapped["Account"] = relationship("Account", back_populates="positions")


class MarketData(Base):
    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    beta: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FxRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pair: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)


class IndustryMapping(Base):
    __tablename__ = "industry_mappings"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=False, default="Unspecified")
