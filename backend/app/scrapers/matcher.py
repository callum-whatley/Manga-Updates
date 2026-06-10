"""
Fuzzy title matching between scraped results and the user's manga list.
Uses rapidfuzz for fast similarity scoring.
"""
import re
try:
    from rapidfuzz import fuzz, process as rfprocess
    HAS_RAPIDFUZZ = True
except ImportError:
    from difflib import SequenceMatcher
    HAS_RAPIDFUZZ = False

AUTO_MATCH_THRESHOLD = 82   # score >= this → auto-linked
SUGGEST_THRESHOLD = 60      # score >= this → surfaced for manual confirmation


def _normalise(title: str) -> str:
    """Lowercase, strip bracketed suffixes, collapse whitespace, remove punctuation."""
    title = title.lower()
    title = re.sub(r'\s*[\(\[].+?[\)\]]', '', title)  # remove (2020), [Official], etc.
    title = re.sub(r'[^\w\s]', '', title)
    return re.sub(r'\s+', ' ', title).strip()


def _score(a: str, b: str) -> float:
    a, b = _normalise(a), _normalise(b)
    if HAS_RAPIDFUZZ:
        return fuzz.WRatio(a, b)
    return SequenceMatcher(None, a, b).ratio() * 100


def match_scraped_to_library(
    scraped: list[dict],
    library_manga: list,  # list of Manga ORM objects
) -> dict:
    """
    Match scraped results against the user's manga library.

    Returns:
        {
            'auto': [{'manga': <Manga>, 'scraped': {...}, 'score': float}],
            'suggest': [{'manga': <Manga>, 'scraped': {...}, 'score': float}],
        }
    """
    auto = []
    suggest = []

    for manga in library_manga:
        best_score = 0.0
        best_scraped = None

        for item in scraped:
            s = _score(manga.title, item['title'])
            if s > best_score:
                best_score = s
                best_scraped = item

        if best_scraped is None:
            continue

        entry = {'manga': manga, 'scraped': best_scraped, 'score': best_score}
        if best_score >= AUTO_MATCH_THRESHOLD:
            auto.append(entry)
        elif best_score >= SUGGEST_THRESHOLD:
            suggest.append(entry)

    return {'auto': auto, 'suggest': suggest}
