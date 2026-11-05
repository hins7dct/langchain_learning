"""东方财富日 K 线接入层。

接口: push2his.eastmoney.com/api/qt/stock/kline/get
要点: data.klines 是逗号分隔的字符串数组，列序见 KLINE_COLS —— 收盘价在最高价之前。
"""

import json
import re
import time
from decimal import Decimal
from typing import Any

import requests

KLINE_API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}

KLINE_COLS = [
    "trade_date", "open_price", "price", "high_price", "low_price",
    "volume", "amount", "amplitude", "pct_chg", "change_amt", "turnover",
]
# 索引: 0日期 1开 2收 3高 4低 5量(手) 6额(元) 7振幅% 8涨跌幅% 9涨跌额 10换手率%

JSONP_RE = re.compile(r"^[\w$.]+\((.*)\);?$", re.S)


def resolve_secid(code: str) -> str:
    """股票代码 -> secid。1.=沪, 0.=深/北。"""
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"1.{code}"
    if code.startswith(("0", "2", "3", "4", "8")):
        return f"0.{code}"
    raise ValueError(f"无法识别市场: {code}")


def _load_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = JSONP_RE.match(text)
    return json.loads(m.group(1) if m else text)


def fetch_klines(
    code: str,
    lmt: int = 500,
    klt: int = 101,
    fqt: int = 1,
    retries: int = 3,
) -> list[dict[str, Any]]:
    """拉取日 K 线，返回按日期升序的结构化列表。

    klt: 101=日 102=周 103=月;  fqt: 0=不复权 1=前复权 2=后复权
    """
    params = {
        "secid": resolve_secid(code),
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": str(klt),
        "fqt": str(fqt),
        "beg": "0",
        "end": "20500101",
        "lmt": str(lmt),
        "_": str(int(time.time() * 1000)),
    }
    last_err: Exception | None = None
    for i in range(retries):
        try:
            resp = requests.get(KLINE_API, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            payload = _load_json(resp.text)
            return _parse_klines(payload)
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"拉取 K 线失败: {code}") from last_err


def _parse_klines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    raw = data.get("klines") or []
    rows: list[dict[str, Any]] = []
    for line in raw:
        parts = line.split(",")
        if len(parts) != len(KLINE_COLS):
            raise ValueError(f"列数不符，期望{len(KLINE_COLS)}，实得{len(parts)}: {line}")
        row = dict(zip(KLINE_COLS, parts))
        row["trade_date"] = row["trade_date"]
        for k in KLINE_COLS[1:]:
            row[k] = _to_decimal(row[k])
        rows.append(row)
    return rows


def _to_decimal(v: str) -> Decimal | None:
    if v in ("-", "", None):
        return None
    return Decimal(v)


def validate(rows: list[dict[str, Any]], tolerance: Decimal = Decimal("0.02")) -> None:
    """三重视检：日期递增 / 昨收连续 / OHLC 关系。任一不过直接抛错。"""
    if not rows:
        raise ValueError("无数据")

    for i, r in enumerate(rows):
        if r["low_price"] is not None and r["high_price"] is not None:
            if not (r["low_price"] <= r["open_price"] <= r["high_price"]):
                raise ValueError(f"[{i}] {r['trade_date']} 开盘价不在高低区间内")
            if not (r["low_price"] <= r["price"] <= r["high_price"]):
                raise ValueError(f"[{i}] {r['trade_date']} 收盘价不在高低区间内")

        if i == 0:
            continue
        prev_close = rows[i - 1]["price"]
        if prev_close is None or r["change_amt"] is None or r["price"] is None:
            continue

        if rows[i]["trade_date"] <= rows[i - 1]["trade_date"]:
            raise ValueError(f"[{i}] 日期未递增: {rows[i - 1]['trade_date']} -> {rows[i]['trade_date']}")

        implied_change = r["price"] - prev_close
        if abs(implied_change - r["change_amt"]) > tolerance:
            raise ValueError(
                f"[{i}] {r['trade_date']} 昨收不连续: "
                f"推导{implied_change} vs 接口{r['change_amt']} —— 列序可能错位"
            )


if __name__ == "__main__":
    rows = fetch_klines("300548", lmt=120)
    validate(rows)

    print(f"共 {len(rows)} 根  {rows[0]['trade_date']} ~ {rows[-1]['trade_date']}")
    print(rows)
    for r in rows[-3:]:
        print(f"{r['trade_date']}  开{r['open_price']} 收{r['price']} "
              f"高{r['high_price']} 低{r['low_price']}  {r['pct_chg']}%")