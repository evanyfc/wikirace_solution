"""
wikirace.py – BFS-based solver that finds the shortest link path between
two Wikipedia articles using the MediaWiki API.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional
import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_BASE = "https://en.wikipedia.org/wiki/"

# How long to wait between API calls (seconds) to be polite to Wikipedia
REQUEST_DELAY = 0.1


def _wiki_url(title: str) -> str:
    """Return the canonical Wikipedia URL for an article title."""
    return WIKI_BASE + title.replace(" ", "_")


def _normalize_title(title: str) -> Optional[str]:
    """
    Resolve a Wikipedia article title to its canonical (redirected) title.
    Returns None if the article does not exist.
    """
    params = {
        "action": "query",
        "titles": title,
        "redirects": 1,
        "format": "json",
        "formatversion": "2",
    }
    try:
        resp = requests.get(WIKI_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None
        page = pages[0]
        if page.get("missing"):
            return None
        return page["title"]
    except requests.RequestException:
        return None


def _get_links(title: str) -> list[str]:
    """
    Return all article-namespace (ns=0) links from a Wikipedia page.
    Handles API pagination via 'plcontinue'.
    """
    links: list[str] = []
    params = {
        "action": "query",
        "prop": "links",
        "titles": title,
        "pllimit": "max",
        "plnamespace": 0,
        "redirects": 1,
        "format": "json",
        "formatversion": "2",
    }
    while True:
        try:
            resp = requests.get(WIKI_API, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Wikipedia API request failed: {exc}") from exc

        data = resp.json()
        pages = data.get("query", {}).get("pages", [])
        for page in pages:
            for link in page.get("links", []):
                links.append(link["title"])

        cont = data.get("continue", {}).get("plcontinue")
        if not cont:
            break
        params["plcontinue"] = cont
        time.sleep(REQUEST_DELAY)

    return links


def find_path(
    start: str,
    end: str,
    max_depth: int = 4,
) -> Optional[list[str]]:
    """
    BFS to find the shortest Wikipedia link path from *start* to *end*.

    Parameters
    ----------
    start:
        Title (or URL) of the starting Wikipedia article.
    end:
        Title (or URL) of the target Wikipedia article.
    max_depth:
        Maximum number of hops to explore before giving up.

    Returns
    -------
    A list of article titles representing the shortest path
    (including both *start* and *end*), or ``None`` if no path was found
    within *max_depth* hops.
    """
    # Strip full URLs to bare titles if the caller passed a URL
    start = _strip_url(start)
    end = _strip_url(end)

    # Resolve redirects
    start_norm = _normalize_title(start)
    end_norm = _normalize_title(end)

    if start_norm is None:
        raise ValueError(f"Wikipedia article not found: '{start}'")
    if end_norm is None:
        raise ValueError(f"Wikipedia article not found: '{end}'")

    if start_norm == end_norm:
        return [start_norm]

    # BFS
    # Each queue entry is a list representing the path taken so far
    queue: deque[list[str]] = deque([[start_norm]])
    visited: set[str] = {start_norm}

    while queue:
        path = queue.popleft()
        current = path[-1]

        if len(path) > max_depth:
            continue

        links = _get_links(current)
        time.sleep(REQUEST_DELAY)

        for link in links:
            if link in visited:
                continue
            new_path = path + [link]
            if link == end_norm:
                return new_path
            visited.add(link)
            if len(new_path) <= max_depth:
                queue.append(new_path)

    return None


def _strip_url(value: str) -> str:
    """Convert a full Wikipedia URL to its article title, if necessary."""
    value = value.strip()
    for prefix in (
        "https://en.wikipedia.org/wiki/",
        "http://en.wikipedia.org/wiki/",
        "en.wikipedia.org/wiki/",
    ):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.replace("_", " ")


def path_with_urls(path: list[str]) -> list[dict]:
    """
    Given a list of article titles (as returned by :func:`find_path`),
    return a list of dicts with ``title`` and ``url`` keys.
    """
    return [{"title": t, "url": _wiki_url(t)} for t in path]
