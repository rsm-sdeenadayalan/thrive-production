"""Region bucketing for job postings: a small, selectable set of location
regions, derived from what the ingested corpus actually contains.

A one-off inspection of the real DB (`JobPosting.objects.values_list
("location", flat=True)`, ~5,900 active postings) shaped the bucket list:
Bay Area (~1,900), Remote (~1,150), New York (~1,180), Seattle (~470), Los
Angeles (~120), San Diego (a handful), a long tail of other US cities/states,
and a large international tail (Tokyo, Singapore, London, Bengaluru, Sao
Paulo, ...). San Diego stays its own bucket despite the small count -- it is
this app's home region and a "0 results" answer for it is itself useful
information, not a bucket worth folding into "Other US" and hiding.
"""

import re

# Order is priority: `region_of` returns the FIRST bucket whose keyword
# appears in the location string. A multi-city posting ("San Francisco, CA |
# New York City, NY") lands in whichever bucket comes first here -- arbitrary
# for that rare case, but deterministic. "Remote" is checked first on
# purpose: a "Remote - US" or "United States - Remote" posting should read as
# Remote, not get swallowed by "Other US".
REGIONS = [
    ("remote", "Remote"),
    ("san_diego", "San Diego"),
    ("bay_area", "Bay Area"),
    ("los_angeles", "Los Angeles"),
    ("seattle", "Seattle"),
    ("new_york", "New York"),
    ("other_us", "Other US"),
    ("international", "International"),
]
REGION_VALUES = {value for value, _label in REGIONS}
REGION_LABELS = dict(REGIONS)

_REMOTE_KEYWORDS = ("remote",)
_SAN_DIEGO_KEYWORDS = ("san diego",)
_BAY_AREA_KEYWORDS = (
    "san francisco", "san jose", "mountain view", "menlo park", "palo alto",
    "sunnyvale", "oakland", "berkeley", "redwood city", "santa clara",
    "bay area",
)
_LOS_ANGELES_KEYWORDS = ("los angeles", "santa monica", "culver city", "burbank")
_SEATTLE_KEYWORDS = ("seattle", "bellevue", "redmond")
_NEW_YORK_KEYWORDS = ("new york", "nyc", "brooklyn")

# A 2-letter state/territory postal code only counts right after a comma
# ("Austin, TX") -- matching it bare would turn common words like "or" and
# "in" (both real US state codes) into false positives on strings like
# "Sydney Or Melbourne" or "Italy or France".
_US_STATE_ABBR = (
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
    "mo", "mt", "ne", "nv", "nh", "nj", "nm", "nc", "nd", "oh", "ok", "or",
    "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wv", "wi", "wy",
    "dc",
)
_US_ABBR_RE = re.compile(r",\s*(" + "|".join(_US_STATE_ABBR) + r")\b")
_US_WORD_RE = re.compile(r"\bus\b")

_US_STATE_NAMES = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota", "tennessee",
    "texas", "utah", "vermont", "virginia", "west virginia", "wisconsin",
    "wyoming",
)
_US_LITERAL_KEYWORDS = ("united states", "usa")


def _contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def _looks_like_us(text):
    if _contains_any(text, _US_LITERAL_KEYWORDS):
        return True
    if _contains_any(text, _US_STATE_NAMES):
        return True
    if _US_ABBR_RE.search(text):
        return True
    return bool(_US_WORD_RE.search(text))


def region_of(location):
    """Bucket one posting's free-text `location` into a selectable region.

    Pure and deterministic -- see `REGIONS` for the priority order and the
    module docstring for the corpus stats that shaped it. Unrecognized or
    blank locations fall to "international": most of the corpus's
    unclassifiable tail genuinely is (Tokyo, Singapore, Sao Paulo, ...), and
    a location this function cannot place is not evidence it is a US one.
    """
    text = (location or "").lower().replace(".", "")
    if _contains_any(text, _REMOTE_KEYWORDS):
        return "remote"
    if _contains_any(text, _SAN_DIEGO_KEYWORDS):
        return "san_diego"
    if _contains_any(text, _BAY_AREA_KEYWORDS):
        return "bay_area"
    if _contains_any(text, _LOS_ANGELES_KEYWORDS):
        return "los_angeles"
    if _contains_any(text, _SEATTLE_KEYWORDS):
        return "seattle"
    if _contains_any(text, _NEW_YORK_KEYWORDS):
        return "new_york"
    if _looks_like_us(text):
        return "other_us"
    return "international"
