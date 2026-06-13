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

    # Build all candidate (manga, scraped_item, score) triples above the threshold.
    candidates = []
    for manga in library_manga:
        for item in scraped:
            s = _score(manga.title, item['title'])
            if s >= SUGGEST_THRESHOLD:
                candidates.append((s, manga, item))

    # Greedy bipartite assignment: sort by score descending, claim each side at most once.
    # manga is keyed by its stable DB primary key; scraped dicts are keyed by object
    # identity (id()) — safe because all items remain alive in `candidates` throughout.
    candidates.sort(key=lambda t: t[0], reverse=True)
    claimed_manga: set[int] = set()
    claimed_scraped: set[int] = set()

    for score, manga, item in candidates:
        manga_key = manga.id
        item_key = id(item)
        if manga_key in claimed_manga or item_key in claimed_scraped:
            continue
        claimed_manga.add(manga_key)
        claimed_scraped.add(item_key)

        entry = {'manga': manga, 'scraped': item, 'score': score}
        if score >= AUTO_MATCH_THRESHOLD:
            auto.append(entry)
        else:
            suggest.append(entry)

    return {'auto': auto, 'suggest': suggest}
