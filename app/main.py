# app/main.py — FareHunter-J (versión con resumen y filtros desde config)
import os
import yaml
import itertools
import datetime as dt

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

    for o, d, m in itertools.product(origins, dests, months):
        for dep in month_date_iter(m, dow_bias):
            for n in stays:
                ret = dep + dt.timedelta(days=int(n))
                if ret <= dep:
                    continue
                yield o, d, dep.isoformat(), ret.isoformat(), m


def extract_best_offers(resp_json, top_k=3):
    """Devuelve hasta top_k ofertas ordenadas por precio (cada una con carrier, stops, price_usd)."""
    data = resp_json.get("data", []) or []
    out = []
    for offer in data:
        try:
            price_usd = float(offer.get("price", {}).get("grandTotal", "inf"))
        except Exception:
            continue
        if price_usd == float("inf"):
            continue

        # Carrier y nº de escalas aproximados: 1er itinerario (ida)
        carrier = "?"
        stops = 0
        try:
            itin1 = offer["itineraries"][0]
            carrier = itin1["segments"][0]["carrierCode"]
            stops = len(itin1["segments"]) - 1
        except Exception:
            pass

        out.append(
            {
                "carrier": carrier,
                "stops": stops,
                "price_usd": price_usd,
                "raw": offer,
            }
        )
    out.sort(key=lambda x: x["price_usd"])
    return out[:top_k]


def format_alert(origin, dest, dep, ret, best, reasons, eur_rate=None):
    usd = best["price_usd"]
    eur = fx_usd_to_eur(usd, eur_rate)
    gfl = google_flights_link(origin, dest, dep, ret)
    deep = airline_deeplink_placeholder(best["carrier"], origin, dest, dep, ret)

    reasons_str = ""
    if reasons:
        friendly = []
        for k, v in reasons.items():
            if k == "hard":
                friendly.append(f"umbral ≤ ${v:.0f}")
            elif k == "near_hard":
                friendly.append(f"cerca del umbral ≤ ${v:.0f}")
            elif k == "p25_baseline":
                friendly.append(f"≤ p25 ${v:.0f}")
            elif k == "delta14":
                friendly.append(f"−15% vs 14d (≤ ${v:.0f})")
            else:
                friendly.append(f"{k}:{v}")
        reasons_str = "\n• Motivos: " + ", ".join(friendly)

    lines = [
        f"✈️ BUSINESS DEAL — {origin} → {dest} ({dep} ➜ {ret})",
        f"• Precio: ${usd:.0f} (~€{eur:.0f})",
        f"• Aerolínea: {best['carrier']}  • Escalas: {best['stops']}",
        f"• Verificar/Comprar: {gfl}",
        f"• Aerolínea: {deep}",
    ]
    if reasons_str:
        lines.append(reasons_str)
    return "\n".join(lines)


def main():
    cfg = load_config()

    # ---- Debug / resumen por run ----
    debug_cfg = cfg.get("debug") or {}
    send_summary = bool(debug_cfg.get("send_run_summary", False))
    top_n_summary = int(debug_cfg.get("top_n", 3))
    best_by_route = {}  # {(O,D): [ {price_usd, dep, ret, carrier, stops}, ... ]}

    # ---- Motor + store + notificador ----
    ama = Amadeus()
    st = Store()
    nt = Notifier()

    # ---- Reglas (lee todos los parámetros desde config.yaml) ----
    rules = Rules(
        cfg.get("price_targets"),
        cfg.get("alert_mode", "smart"),
        cfg.get("default_price_target"),
        cfg.get("soft_margin_pct"),
    )

    max_stops = int(cfg.get("max_stops", 1))
    airlines_whitelist = set(cfg.get("airlines_whitelist") or [])  # opcional

    searches = list(iter_searches(cfg))
    for origin, dest, dep, ret, month_iso in searches:
        try:
            resp = ama.search_roundtrip_business(
                origin, dest, dep, ret, max_stops=max_stops
            )
            best_list = extract_best_offers(resp, top_k=3)
            if not best_list:
                continue

            # Filtra por whitelist de aerolíneas si se definió
            if airlines_whitelist:
                best_list = [b for b in best_list if b["carrier"] in airlines_whitelist]
                if not best_list:
                    continue

            best = best_list[0]

            # Guarda histórico
            st.add_quote(
                origin,
                dest,
                dep,
                ret,
                best["carrier"],
                best["stops"],
                best["price_usd"],
                "J",
            )

            # Para resumen
            rk = (origin, dest)
            best_by_route.setdefault(rk, [])
            best_by_route[rk].append(
                {
                    "price_usd": best["price_usd"],
                    "dep": dep,
                    "ret": ret,
                    "carrier": best["carrier"],
                    "stops": best["stops"],
                }
            )
            best_by_route[rk] = sorted(
                best_by_route[rk], key=lambda x: x["price_usd"]
            )[:top_n_summary]

            # Veredicto (hard_only, near_hard o smart)
            recent = st.recent_prices(origin, dest, month_iso)
            reasons = rules.is_deal(origin, dest, best["price_usd"], recent)
            if reasons:
                # De-dup: evita spam de la misma combinación por 72h
                key = st.dedup_key(
                    origin,
                    dest,
                    dep,
                    ret,
                    best["carrier"],
                    best["price_usd"],
                )
                if not st.was_alerted_recently(key):
                    msg = format_alert(origin, dest, dep, ret, best, reasons)
                    nt.send(msg)
                    st.mark_alerted(key)

        except Exception as e:
            # Log minimal y continúa
            print("ERROR en", origin, dest, dep, ret, "::", e)

    # ---- Resumen por run (opcional) ----
    if send_summary and best_by_route:
        lines = ["📊 Resumen FareHunter — mejores precios del run:"]
        for (o, d), items in sorted(best_by_route.items()):
            lines.append(f"\n{o} → {d}:")
            for it in items:
                lines.append(
                    f"  • ${it['price_usd']:.0f} — {it['dep']}→{it['ret']} — {it['carrier']} ({it['stops']} esc.)"
                )
        nt.send("\n".join(lines))


if __name__ == "__main__":
    main()
