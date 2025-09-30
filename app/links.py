def google_flights_link(origin: str, dest: str, dep: str, ret: str, cabin: str = "business") -> str:
    return f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{dep}%20through%20{ret}%20{cabin}"

def airline_deeplink_placeholder(carrier: str, origin: str, dest: str, dep: str, ret: str) -> str:
    return f"https://www.{carrier.lower()}.com/"
