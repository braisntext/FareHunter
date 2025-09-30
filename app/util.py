from __future__ import annotations
import os, math, pytz, datetime as dt
from typing import List, Iterable, Tuple

TZ = os.getenv("TZ", "UTC")
_DOW = {"Mon":0,"Tue":1,"Wed":2,"Thu":3,"Fri":4,"Sat":5,"Sun":6}

def expand_month(month_str: str) -> Tuple[dt.date, dt.date]:
    d = dt.date.fromisoformat(month_str)
    first = d.replace(day=1)
    if first.month == 12:
        next_first = first.replace(year=first.year+1, month=1)
    else:
        next_first = first.replace(month=first.month+1)
    last = next_first - dt.timedelta(days=1)
    return first, last

def month_date_iter(month_str: str, dow_bias: List[str] | None = None) -> Iterable[dt.date]:
    first, last = expand_month(month_str)
    for i in range((last - first).days + 1):
        day = first + dt.timedelta(days=i)
        if dow_bias:
            if day.weekday() in { _DOW[d] for d in dow_bias if d in _DOW }:
                yield day
        else:
            yield day

def percentile(values: List[float], p: float) -> float:
    if not values: return math.inf
    values = sorted(values)
    k = (len(values)-1) * (p/100.0)
    f = math.floor(k); c = math.ceil(k)
    if f == c: return values[int(k)]
    return values[f] + (values[c]-values[f])*(k-f)

def fx_usd_to_eur(usd: float, rate: float | None = None) -> float:
    try:
        rate = float(os.getenv("USD_EUR_RATE", "0.92")) if rate is None else float(rate)
    except: rate = 0.92
    return round(usd * rate, 2)
