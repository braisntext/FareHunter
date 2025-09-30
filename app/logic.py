from .util import percentile

class Rules:
    def __init__(self, price_targets=None):
        self.pt = price_targets or {}
    def route_key(self, origin: str, dest: str) -> str:
        return f"{origin}-{dest}"
    def is_deal(self, origin: str, dest: str, price_usd: float, recent_prices: list[float]):
        rk = self.route_key(origin, dest)
        hard = self.pt.get(rk)
        p25 = percentile(recent_prices, 25) if recent_prices else None
        verdict, reasons = False, {}
        if hard and price_usd <= hard: verdict=True; reasons["hard"]=hard
        if p25 and price_usd <= p25: verdict=True; reasons["p25_baseline"]=p25
        if recent_prices:
            best14 = min(recent_prices[:50])
            if price_usd <= 0.85*best14: verdict=True; reasons["delta14"]=round(0.85*best14,2)
        return reasons if verdict else None
