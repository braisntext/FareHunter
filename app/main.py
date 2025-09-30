import os, yaml, itertools, datetime as dt
from .amadeus import Amadeus
from .store import Store
from .notify import Notifier
from .logic import Rules
from .util import month_date_iter, fx_usd_to_eur
from .links import google_flights_link, airline_deeplink_placeholder

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def iter_searches(cfg):
    origins = cfg.get("origins", [])
    dests = cfg.get("destinations", [])
    months = cfg.get("months", [])
    stays = cfg.get("stays_nights", [7])
    dow_bias = cfg.get("dow_bias")
    for o,d,m in itertools.product(origins, dests, months):
        for dep in month_date_iter(m, dow_bias):
            for n in stays:
                ret = dep + dt.timedelta(days=int(n))
                if ret <= dep: continue
                yield o,d,dep.isoformat(), ret.isoformat(), m

def extract_best_offer(resp_json):
    data = resp_json.get("data", [])
    out = []
    for offer in data:
        try:
            price_usd = float(offer.get("price",{}).get("grandTotal","inf"))
        except: 
            continue
        try:
            itin1 = offer["itineraries"][0]
            carrier = itin1["segments"][0]["carrierCode"]
            stops = len(itin1["segments"]) - 1
        except Exception:
            carrier, stops = "?", 0
        out.append({"carrier": carrier, "stops": stops, "price_usd": price_usd, "raw": offer})
    out.sort(key=lambda x: x["price_usd"])
    return out[:3]

def format_alert(origin, dest, dep, ret, best, eur_rate=None):
    usd = best["price_usd"]; eur = fx_usd_to_eur(usd, eur_rate)
    gfl = google_flights_link(origin, dest, dep, ret)
    deep = airline_deeplink_placeholder(best["carrier"], origin, dest, dep, ret)
    return "\n".join([
        f"✈️ BUSINESS DEAL — {origin} → {dest} ({dep} ➜ {ret})",
        f"• Precio: ${usd:.0f} (~€{eur:.0f})",
        f"• Aerolínea: {best['carrier']}  • Escalas: {best['stops']}",
        f"• Verificar/Comprar: {gfl}",
        f"• Aerolínea: {deep}",
    ])

def main():
    cfg = load_config()
    ama = Amadeus()
    st = Store()
    nt = Notifier()
    rules = Rules(cfg.get("price_targets"))
    max_stops = int(cfg.get("max_stops", 1))

    for origin, dest, dep, ret, month_iso in iter_searches(cfg):
        try:
            resp = ama.search_roundtrip_business(origin, dest, dep, ret, max_stops=max_stops)
            best3 = extract_best_offer(resp)
            if not best3: continue
            best = best3[0]
            st.add_quote(origin, dest, dep, ret, best["carrier"], best["stops"], best["price_usd"], "J")
            recent = st.recent_prices(origin, dest, month_iso)
            verdict = rules.is_deal(origin, dest, best["price_usd"], recent)
            if verdict:
                key = st.dedup_key(origin, dest, dep, ret, best["carrier"], best["price_usd"])
                if not st.was_alerted_recently(key):
                    msg = format_alert(origin, dest, dep, ret, best)
                    mot = ", ".join([f"{k}≤{v:.0f}" for k,v in verdict.items()])
                    nt.send(msg + (f"\n• Motivos: {mot}" if mot else ""))
                    st.mark_alerted(key)
        except Exception as e:
            print("ERROR en", origin, dest, dep, ret, "::", e)

if __name__ == "__main__":
    main()
