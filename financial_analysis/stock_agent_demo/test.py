import json
import re
import time

import requests

API = 'https://pushguest.eastmoney.com/api/qt/clist/get'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    ),
    'Referer': 'https://quote.eastmoney.com/',
}

# fltt=1 -> 价格/比率字段为整数，需除以 100；fltt=2 -> 直接是小数
FLTT = 1
SCALE = 100 if FLTT == 1 else 1

FIELDS = 'f12,f13,f14,f1,f2,f4,f3,f152,f5,f6,f7,f15,f18,f16,f17,f10,f8,f9,f23'

PARAMS = {
    'np': '1',
    'fltt': str(FLTT),
    'invt': '2',
    # m:0+t:6 = 深A主板, m:0+t:80 = 深A创业板, m:1+t:2 = 沪A主板,
    # m:1+t:23 = 沪A科创板, m:0+t:81 = 北交所
    'fs': 'm:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:81+s:262144+f:!2',
    'fields': FIELDS,
    'fid': 'f3',
    'pn': '279',
    'pz': '20',
    'po': '1',
    'dect': '1',
    'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
    'wbp2u': '|0|0|0|web',
    '_': str(int(time.time() * 1000)),
}

JSONP_RE = re.compile(r'^[\w$.]+\((.*)\);?$', re.S)


def parse_jsonp(text):
    text = text.strip()
    m = JSONP_RE.match(text)
    return json.loads(m.group(1) if m else text)


def fetch_page(pn=1, pz=20, fid='f3', po=1):
    params = dict(PARAMS, pn=str(pn), pz=str(pz), fid=fid, po=str(po),
                  _=str(int(time.time() * 1000)))
    resp = requests.get(API, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return parse_jsonp(resp.text)


def to_num(value, scale=SCALE):
    if value in ('-', '', None):
        return None
    try:
        return round(int(value) / scale, 2) if scale != 1 else round(float(value), 2)
    except (TypeError, ValueError):
        return None


def to_row(item):
    return {
        'code': item.get('f12'),
        'market': item.get('f13'),          # 0=深, 1=沪
        'name': item.get('f14'),
        'price': to_num(item.get('f2')),    # 最新价
        'change': to_num(item.get('f4')),   # 涨跌额
        'pct': to_num(item.get('f3')),      # 涨跌幅 %
        'volume': item.get('f5'),           # 成交量(手)
        'amount': item.get('f6'),           # 成交额(元)
        'amplitude': to_num(item.get('f7')),# 振幅 %
        'high': to_num(item.get('f15')),
        'low': to_num(item.get('f16')),
        'open': to_num(item.get('f17')),
        'pre_close': to_num(item.get('f18')),
        'turnover': to_num(item.get('f8')), # 换手率 %
        'pe': to_num(item.get('f9')),       # 市盈率(动)
        'pb': to_num(item.get('f23')),      # 市净率
        'vol_ratio': to_num(item.get('f10')),  # 量比
    }


if __name__ == '__main__':
    data = fetch_page(pn=1, pz=20)
    # data 结构: {"rc":0,"rt":6,"svr":...,"data":{"total":5000,"diff":[...]}}
    payload = data.get('data') or {}
    print('总数:', payload.get('total'))

    for row in map(to_row, payload.get('diff') or []):
        print(row)
