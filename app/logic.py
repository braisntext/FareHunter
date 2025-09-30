# app/logic.py
from .util import percentile

class Rules:
    def __init__(self, price_targets=None, alert_mode="smart", default_price_target=None):
        self.pt = price_targets or {}
        self.alert_mode = (alert_mode or "smart").strip().lower()
        self.default_pt = default_price_target  # opcional

    def route_key(self, origin: str, dest: str) -> str:
        return f"{origin}-{dest}"

    def _hard_threshold(self, origin: str, dest: str):
        rk = self.route_key(origin, dest)
        if rk in self.pt: 
            return float(self.pt[rk])
        if self.default_pt is not None:
            return float(self.default_pt)
        return None

    def is_deal(self, origin: str, dest: str, price_usd: float, recent_prices: list[float]):
        # MODO ESTRICTO: solo dispara si price < hard target
        if self.alert_mode == "hard_only":
            hard = self._hard_threshold(origin, dest)
            if hard is None:
                return None  # sin umbral para esta ruta → no alertar
            return {"hard": hard} if price_usd <= hard else None

        # MODO SMART: umbral + señales estadísticas
        reasons = {}
        hard = self._hard_threshold(origin, dest)
        verdict = False
        if hard is not None and price_usd <= hard:
            verdict = True; reasons["hard"] = hard
        if recent_prices:
            p25 = percentile(recent_prices, 25)
            if price_usd <= p25:
                verdict = True; reasons["p25_baseline"] = float(p25)
            best14 = min(recent_prices[:50])
            if price_usd <= 0.85 * best14:
                verdict = True; reasons["delta14"] = round(0.85*best14, 2)
        return reasons if verdict else None
