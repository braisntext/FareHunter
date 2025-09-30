import os, requests

AMADEUS_BASE = os.getenv("AMADEUS_BASE", "https://test.api.amadeus.com")

class Amadeus:
    def __init__(self, key: str | None = None, secret: str | None = None):
        self.key = key or os.getenv("AMADEUS_KEY")
        self.secret = secret or os.getenv("AMADEUS_SECRET")
        if not self.key or not self.secret:
            raise RuntimeError("Faltan AMADEUS_KEY/AMADEUS_SECRET")
        self.token = None

    def auth(self):
        r = requests.post(
            f"{AMADEUS_BASE}/v1/security/oauth2/token",
            data={"grant_type":"client_credentials","client_id": self.key,"client_secret": self.secret},
            timeout=20)
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def _hdr(self):
        if not self.token: self.auth()
        return {"Authorization": f"Bearer {self.token}", "Content-Type":"application/json"}

    def search_roundtrip_business(self, origin: str, dest: str, dep_date: str, ret_date: str, max_stops: int = 1):
        body = {
          "currencyCode": "USD",
          "originDestinations": [
            {"id": "1","originLocationCode": origin,"destinationLocationCode": dest,"departureDateTimeRange": {"date": dep_date}},
            {"id": "2","originLocationCode": dest,"destinationLocationCode": origin,"departureDateTimeRange": {"date": ret_date}}
          ],
          "travelers": [{"id":"1","travelerType":"ADULT"}],
          "sources": ["GDS"],
          "searchCriteria": {
            "maxFlightOffers": 40,
            "flightFilters": {
              "cabinRestrictions": [{"cabin": "BUSINESS","coverage": "MOST_SEGMENTS","originDestinationIds": ["1","2"]}],
              "connectionRestriction": {"maxNumberOfConnections": max_stops}
            }
          }
        }
        url = f"{AMADEUS_BASE}/v2/shopping/flight-offers"
        r = requests.post(url, headers=self._hdr(), json=body, timeout=40)
        if r.status_code == 401:
            self.auth(); r = requests.post(url, headers=self._hdr(), json=body, timeout=40)
        r.raise_for_status()
        return r.json()
