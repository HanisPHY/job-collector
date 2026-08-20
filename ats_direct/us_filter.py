"""
US-location filter for ATS jobs (--us-only, ON by default).

Design mandated by dual review (2026-08-19):
  - blocklist with keep-on-uncertainty, NOT an allowlist (location text is
    messy free-form: "SF, NYC", "US, OR, Hillsboro", "Remote", "")
  - US-marker PRECEDENCE: reject only when a non-US marker matches AND no
    US marker matches. This rescues "Vancouver, WA", "Dublin, CA",
    "London, OH" and multi-location strings like "SF, NYC, London".
  - never blocklist bare 2-letter country codes (IN/DE/CA collide with
    Indiana/Delaware/California)
  - location field only - never the title ("New Grad - UK Government" can
    be a US-based posting)
"""

import re

# US signals. State codes are matched case-SENSITIVELY and only in
# list-position (after comma/start) to avoid hitting words like "in".
_US_TOKENS = re.compile(
    r"\b(?:USA?|U\.S\.A?\.?|United\s+States|America)\b", re.I)
_US_STATE = re.compile(
    r"(?:^|,\s*|\s)(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|"
    r"ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|"
    r"TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)(?:$|,|\s)")
_US_CITIES = re.compile(
    r"\b(?:San\s+Francisco|New\s+York|NYC|SF\b|Seattle|Austin|Boston|Chicago|"
    r"Denver|Atlanta|Miami|Dallas|Houston|Phoenix|Portland|Philadelphia|"
    r"Mountain\s+View|Palo\s+Alto|Sunnyvale|Menlo\s+Park|Santa\s+Clara|"
    r"San\s+Jose|San\s+Diego|Los\s+Angeles|Cupertino|Redmond|Bellevue|"
    r"Irvine|Pittsburgh|Raleigh|Nashville|Salt\s+Lake|Bay\s+Area)\b", re.I)

# Non-US signals: countries spelled out + unambiguous foreign cities.
# Ambiguous city names (Vancouver, Dublin, Toronto, Paris, Berlin) appear
# only with their country/province qualifier - the precedence rule protects
# their US namesakes anyway, but qualified forms keep intent explicit.
_NON_US = re.compile(
    r"\b(?:United\s+Kingdom|England|Scotland|Ireland|Germany|France|Spain|"
    r"Portugal|Poland|Netherlands|Switzerland|Sweden|Denmark|Norway|Finland|"
    r"Austria|Belgium|Italy|Czech|Romania|Hungary|Ukraine|India|China|Japan|"
    r"Korea|Taiwan|Singapore|Vietnam|Philippines|Indonesia|Malaysia|Thailand|"
    r"Australia|New\s+Zealand|Canada|Mexico|Brazil|Argentina|Colombia|Chile|"
    r"Israel|Turkey|Egypt|Nigeria|Kenya|South\s+Africa|UAE|Emirates|Saudi|"
    r"London|Cambridge,\s*UK|Beijing|Shanghai|Shenzhen|Hangzhou|Guangzhou|"
    r"Hong\s+Kong|Bangalore|Bengaluru|Hyderabad|Mumbai|Pune|Chennai|Delhi|"
    r"Noida|Gurgaon|Tokyo|Osaka|Seoul|Taipei|Sydney|Melbourne|Auckland|"
    r"S[aã]o\s+Paulo|Mexico\s+City|Guadalajara|Monterrey|Bogot[aá]|"
    r"Buenos\s+Aires|Warsaw|Krakow|Wroclaw|Amsterdam|Rotterdam|Munich|"
    r"Frankfurt|Hamburg|Zurich|Geneva|Stockholm|Copenhagen|Oslo|Helsinki|"
    r"Madrid|Barcelona|Lisbon|Milan|Rome|Prague|Bucharest|Budapest|Vienna|"
    r"Brussels|Tel\s+Aviv|Istanbul|Dubai|Cairo|Lagos|Nairobi|Cape\s+Town|"
    r"Vancouver,\s*BC|Toronto,\s*ON|Dublin,\s*Ireland|Montreal|Ottawa|"
    r"Calgary|Edmonton|Waterloo,\s*ON)\b", re.I)


def is_probably_us(location: str) -> bool:
    """True unless the location clearly names a non-US place with no US signal."""
    if not location or not location.strip():
        return True  # keep-on-uncertainty
    loc = location.strip()
    if _US_TOKENS.search(loc) or _US_STATE.search(loc) or _US_CITIES.search(loc):
        return True  # US marker takes precedence over any non-US marker
    return not _NON_US.search(loc)
