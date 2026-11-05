"""ORM 模型：与 schema.sql 逐字段对应。

约定：
    - 只声明结构 + 纯内存逻辑，不写任何需要 session 的方法
    - 价格/金额一律 Numeric（Python 端是 Decimal），绝不用 float
    - 约束名与 schema.sql 完全一致，方便后续接 Alembic
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum, StrEnum

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Market(IntEnum):
    """与 stock.market 列对应。纯 Python 常量，不映射成 PG enum。"""

    SZ = 0
    SH = 1


class Board(StrEnum):
    SZ_MAIN = "深市主板"
    SH_MAIN = "沪市主板"
    GEM = "创业板"
    STAR = "科创板"
    BSE = "北交所"


def infer_board(code: str) -> Board | None:
    """由代码前缀推断板块。clist 快照不返回板块字段，只能这样补。"""
    if code.startswith(("688", "689")):
        return Board.STAR
    if code.startswith("6"):
        return Board.SH_MAIN
    if code.startswith(("300", "301")):
        return Board.GEM
    if code.startswith(("000", "001", "002", "003")):
        return Board.SZ_MAIN
    if code.startswith(("43", "83", "87", "92")):
        return Board.BSE
    return None


class Stock(Base):
    """股票维度表。"""

    __tablename__ = "stock"
    __table_args__ = (
        UniqueConstraint("market", "code", name="uq_stock_market_code"),
        {"comment": "股票基础信息（维度表）"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    market: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="0=深交所, 1=上交所")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    board: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    quotes: Mapped[list["StockQuote"]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Stock {self.market}.{self.code} {self.name}>"


class StockQuote(Base):
    """行情日快照事实表：每只股票每个交易日一条。"""

    __tablename__ = "stock_quote"
    __table_args__ = (
        UniqueConstraint("stock_id", "trade_date", name="uq_quote_stock_date"),
        Index("idx_quote_date_stock", "trade_date", "stock_id"),
        Index("idx_quote_stock_date", text("stock_id, trade_date DESC")),
        {"comment": "行情日快照（事实表）"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stock.id", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), comment="最新价")
    change_amt: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    volume: Mapped[int | None] = mapped_column(BigInteger, comment="成交量（手）")
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), comment="成交额（元）")
    amplitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    pe: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    pb: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    vol_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    stock: Mapped["Stock"] = relationship(back_populates="quotes")

    @property
    def is_up(self) -> bool | None:
        """纯内存计算，放模型里没问题（不需要 session）。"""
        if self.change_amt is None:
            return None
        return self.change_amt > 0

    def __repr__(self) -> str:
        return f"<StockQuote stock_id={self.stock_id} {self.trade_date} {self.price}>"


class FetchBatch(Base):
    """抓取批次日志，用于定位哪一页/哪一批出错并重跑。"""

    __tablename__ = "fetch_batch"
    __table_args__ = ({"comment": "每次抓取的批次日志，便于排查与重跑"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'eastmoney_clist'")
    )
    page_no: Mapped[int | None] = mapped_column(nullable=True)
    page_size: Mapped[int | None] = mapped_column(nullable=True)
    row_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<FetchBatch {self.source} p{self.page_no} {self.status}>"