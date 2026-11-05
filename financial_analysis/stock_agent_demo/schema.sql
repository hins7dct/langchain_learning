-- 股票维度表
CREATE TABLE IF NOT EXISTS stock (
    id          bigserial    PRIMARY KEY,
    code        varchar(10)  NOT NULL,
    market      smallint     NOT NULL,
    name        varchar(64)  NOT NULL,
    board       varchar(16),
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_stock_market_code UNIQUE (market, code)
);
COMMENT ON TABLE  stock          IS '股票基础信息（维度表）';
COMMENT ON COLUMN stock.market   IS '0=深交所, 1=上交所';
COMMENT ON COLUMN stock.board    IS '沪市主板/深市主板/创业板/科创板/北交所';

-- 行情快照事实表（每只股票每个交易日一条）
CREATE TABLE IF NOT EXISTS stock_quote (
    id           bigserial     PRIMARY KEY,
    stock_id     bigint        NOT NULL REFERENCES stock (id) ON DELETE CASCADE,
    trade_date   date          NOT NULL,
    snapshot_at  timestamptz   NOT NULL,
    price        numeric(12,3),
    change_amt   numeric(12,3),
    pct_chg      numeric(8,3),
    open_price   numeric(12,3),
    high_price   numeric(12,3),
    low_price    numeric(12,3),
    pre_close    numeric(12,3),
    volume       bigint,
    amount       numeric(20,2),
    amplitude    numeric(8,3),
    turnover     numeric(8,3),
    pe           numeric(12,3),
    pb           numeric(12,3),
    vol_ratio    numeric(10,3),
    created_at   timestamptz   NOT NULL DEFAULT now(),
    updated_at   timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT uq_quote_stock_date UNIQUE (stock_id, trade_date)
);
COMMENT ON TABLE  stock_quote            IS '行情日快照（事实表）';
COMMENT ON COLUMN stock_quote.price      IS '最新价';
COMMENT ON COLUMN stock_quote.volume     IS '成交量（手）';
COMMENT ON COLUMN stock_quote.amount     IS '成交额（元）';
COMMENT ON COLUMN stock_quote.snapshot_at IS '本条数据的抓取时刻';

CREATE INDEX IF NOT EXISTS idx_quote_date_stock ON stock_quote (trade_date, stock_id);
CREATE INDEX IF NOT EXISTS idx_quote_stock_date ON stock_quote (stock_id, trade_date DESC);

-- 抓取批次日志
CREATE TABLE IF NOT EXISTS fetch_batch (
    id           bigserial    PRIMARY KEY,
    source       varchar(32)  NOT NULL DEFAULT 'eastmoney_clist',
    page_no      integer,
    page_size    integer,
    row_count    integer      NOT NULL DEFAULT 0,
    status       varchar(16)  NOT NULL,
    error        text,
    started_at   timestamptz  NOT NULL DEFAULT now(),
    finished_at  timestamptz
);
COMMENT ON TABLE fetch_batch IS '每次抓取的批次日志，便于排查与重跑';