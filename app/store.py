import sqlite3, os, time

DB_PATH = os.getenv("DB_PATH", "db.sqlite")

DDL = """CREATE TABLE IF NOT EXISTS quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  origin TEXT, dest TEXT, dep TEXT, ret TEXT,
  carrier TEXT, stops INTEGER, price_usd REAL, cabin TEXT, found_at INTEGER
);
CREATE TABLE IF NOT EXISTS alerts_sent ( key TEXT PRIMARY KEY, sent_at INTEGER );
"""

class Store:
    def __init__(self, path: str = DB_PATH):
        self.path = path; self._ensure()
    def _ensure(self):
        with sqlite3.connect(self.path) as con: con.executescript(DDL)
    def add_quote(self, origin, dest, dep, ret, carrier, stops, price_usd, cabin="J"):
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO quotes(origin,dest,dep,ret,carrier,stops,price_usd,cabin,found_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (origin,dest,dep,ret,carrier,stops,price_usd,cabin,int(time.time())))
    def recent_prices(self, origin, dest, month_iso: str) -> list[float]:
        y,m,_ = month_iso.split("-")
        with sqlite3.connect(self.path) as con:
            cur = con.execute("SELECT price_usd FROM quotes WHERE origin=? AND dest=? AND substr(dep,1,7)=? ORDER BY found_at DESC LIMIT 500",
                              (origin, dest, f"{y}-{m}"))
            return [r[0] for r in cur.fetchall()]
    def dedup_key(self, origin, dest, dep, ret, carrier, price_usd) -> str:
        return f"{origin}-{dest}-{dep}-{ret}-{carrier}-{round(price_usd)}"
    def was_alerted_recently(self, key: str, within_hours=72) -> bool:
        with sqlite3.connect(self.path) as con:
            cur = con.execute("SELECT sent_at FROM alerts_sent WHERE key=?", (key,))
            row = cur.fetchone()
            return bool(row) and (int(time.time()) - row[0] < within_hours*3600)
    def mark_alerted(self, key: str):
        with sqlite3.connect(self.path) as con:
            con.execute("REPLACE INTO alerts_sent(key,sent_at) VALUES (?,?)", (key, int(time.time())))
