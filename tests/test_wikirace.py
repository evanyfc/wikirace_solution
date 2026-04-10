"""
tests/test_wikirace.py

Unit tests for the WikiRace solver.

Network calls are mocked so the tests run quickly and offline.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_links_response(*titles):
    """Build a fake MediaWiki API response for action=query&prop=links."""
    return {
        "query": {
            "pages": [
                {
                    "title": "FakePage",
                    "links": [{"title": t} for t in titles],
                }
            ]
        }
    }


def _make_normalize_response(title, missing=False):
    """Build a fake MediaWiki API response for action=query (title resolution)."""
    page: dict = {"title": title}
    if missing:
        page["missing"] = True
    return {"query": {"pages": [page]}}


# ── wikirace module ───────────────────────────────────────────────────────────

class TestStripUrl:
    def test_full_https_url(self):
        from wikirace import _strip_url
        assert _strip_url("https://en.wikipedia.org/wiki/Python_(programming_language)") == "Python (programming language)"

    def test_http_url(self):
        from wikirace import _strip_url
        assert _strip_url("http://en.wikipedia.org/wiki/Python") == "Python"

    def test_bare_title(self):
        from wikirace import _strip_url
        assert _strip_url("  Python  ") == "Python"

    def test_underscores_converted(self):
        from wikirace import _strip_url
        assert _strip_url("Albert_Einstein") == "Albert Einstein"


class TestPathWithUrls:
    def test_returns_list_of_dicts(self):
        from wikirace import path_with_urls
        result = path_with_urls(["Albert Einstein", "Physics"])
        assert result == [
            {"title": "Albert Einstein", "url": "https://en.wikipedia.org/wiki/Albert_Einstein"},
            {"title": "Physics", "url": "https://en.wikipedia.org/wiki/Physics"},
        ]

    def test_empty_path(self):
        from wikirace import path_with_urls
        assert path_with_urls([]) == []


class TestNormalizeTitle:
    @patch("wikirace.requests.get")
    def test_returns_title_for_existing_article(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _make_normalize_response("Python (programming language)"),
            raise_for_status=lambda: None,
        )
        from wikirace import _normalize_title
        assert _normalize_title("Python") == "Python (programming language)"

    @patch("wikirace.requests.get")
    def test_returns_none_for_missing_article(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _make_normalize_response("NonExistent", missing=True),
            raise_for_status=lambda: None,
        )
        from wikirace import _normalize_title
        assert _normalize_title("NonExistent") is None

    @patch("wikirace.requests.get")
    def test_returns_none_on_network_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("timeout")
        from wikirace import _normalize_title
        assert _normalize_title("Anything") is None


class TestGetLinks:
    @patch("wikirace.requests.get")
    def test_returns_links(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _make_links_response("PageA", "PageB", "PageC"),
            raise_for_status=lambda: None,
        )
        from wikirace import _get_links
        links = _get_links("SomePage")
        assert "PageA" in links
        assert "PageB" in links
        assert "PageC" in links

    @patch("wikirace.requests.get")
    def test_raises_on_network_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("connection error")
        from wikirace import _get_links
        with pytest.raises(RuntimeError, match="Wikipedia API request failed"):
            _get_links("SomePage")


class TestFindPath:
    """Tests for the main BFS find_path function."""

    def _norm_side_effect(self, title_map):
        """
        Build a side_effect for mocked requests.get that handles both
        normalize calls (action=query without prop=links) and link calls.
        """
        import json

        def side_effect(url, params=None, **kwargs):
            params = params or {}
            titles = params.get("titles", "")
            mock = MagicMock()
            mock.raise_for_status = lambda: None

            if params.get("prop") == "links":
                links = title_map.get(titles, [])
                mock.json = lambda: _make_links_response(*links)
            else:
                canonical = titles  # trivial: title resolves to itself
                mock.json = lambda: _make_normalize_response(canonical)

            return mock

        return side_effect

    @patch("wikirace.time.sleep")
    @patch("wikirace.requests.get")
    def test_same_start_and_end(self, mock_get, mock_sleep):
        mock_get.side_effect = self._norm_side_effect({})
        from wikirace import find_path
        path = find_path("Python", "Python")
        assert path == ["Python"]

    @patch("wikirace.time.sleep")
    @patch("wikirace.requests.get")
    def test_direct_link(self, mock_get, mock_sleep):
        """A → B in one hop."""
        link_map = {"A": ["B", "C"]}
        mock_get.side_effect = self._norm_side_effect(link_map)
        from wikirace import find_path
        path = find_path("A", "B")
        assert path == ["A", "B"]

    @patch("wikirace.time.sleep")
    @patch("wikirace.requests.get")
    def test_two_hops(self, mock_get, mock_sleep):
        """A → B → C."""
        link_map = {"A": ["B"], "B": ["C"]}
        mock_get.side_effect = self._norm_side_effect(link_map)
        from wikirace import find_path
        path = find_path("A", "C")
        assert path == ["A", "B", "C"]

    @patch("wikirace.time.sleep")
    @patch("wikirace.requests.get")
    def test_no_path_returns_none(self, mock_get, mock_sleep):
        """No link exists; should return None within depth limit."""
        link_map = {"A": ["X"], "X": ["Y"]}  # C is unreachable
        mock_get.side_effect = self._norm_side_effect(link_map)
        from wikirace import find_path
        path = find_path("A", "C", max_depth=2)
        assert path is None

    @patch("wikirace.time.sleep")
    @patch("wikirace.requests.get")
    def test_raises_for_missing_start(self, mock_get, mock_sleep):
        """Should raise ValueError when the start article does not exist."""

        def side_effect(url, params=None, **kwargs):
            params = params or {}
            titles = params.get("titles", "")
            mock = MagicMock()
            mock.raise_for_status = lambda: None
            if titles == "BadStart":
                mock.json = lambda: _make_normalize_response("BadStart", missing=True)
            else:
                mock.json = lambda: _make_normalize_response(titles)
            return mock

        mock_get.side_effect = side_effect
        from wikirace import find_path
        with pytest.raises(ValueError, match="not found"):
            find_path("BadStart", "SomeEnd")

    @patch("wikirace.time.sleep")
    @patch("wikirace.requests.get")
    def test_raises_for_missing_end(self, mock_get, mock_sleep):
        """Should raise ValueError when the end article does not exist."""

        def side_effect(url, params=None, **kwargs):
            params = params or {}
            titles = params.get("titles", "")
            mock = MagicMock()
            mock.raise_for_status = lambda: None
            if titles == "BadEnd":
                mock.json = lambda: _make_normalize_response("BadEnd", missing=True)
            else:
                mock.json = lambda: _make_normalize_response(titles)
            return mock

        mock_get.side_effect = side_effect
        from wikirace import find_path
        with pytest.raises(ValueError, match="not found"):
            find_path("GoodStart", "BadEnd")

    @patch("wikirace.time.sleep")
    @patch("wikirace.requests.get")
    def test_bfs_finds_shortest_path(self, mock_get, mock_sleep):
        """BFS should return the shortest path, not just any path."""
        # Graph:  A → B → C (2 hops)
        #         A → C     (1 hop, direct)
        link_map = {"A": ["B", "C"], "B": ["C"]}
        mock_get.side_effect = self._norm_side_effect(link_map)
        from wikirace import find_path
        path = find_path("A", "C")
        assert path == ["A", "C"]  # direct, not A→B→C


# ── Flask app ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


class TestFlaskApp:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"WikiRace" in resp.data

    def test_search_missing_params(self, client):
        resp = client.post("/search", data={"start": "", "end": ""})
        assert resp.status_code == 200
        assert b"Please enter both" in resp.data

    @patch("app.find_path")
    def test_search_no_path_found(self, mock_fp, client):
        mock_fp.return_value = None
        resp = client.post("/search", data={"start": "A", "end": "B", "max_depth": "2"})
        assert resp.status_code == 200
        assert b"No path found" in resp.data

    @patch("app.find_path")
    @patch("app.path_with_urls")
    def test_search_shows_result(self, mock_pwu, mock_fp, client):
        mock_fp.return_value = ["A", "B", "C"]
        mock_pwu.return_value = [
            {"title": "A", "url": "https://en.wikipedia.org/wiki/A"},
            {"title": "B", "url": "https://en.wikipedia.org/wiki/B"},
            {"title": "C", "url": "https://en.wikipedia.org/wiki/C"},
        ]
        resp = client.post("/search", data={"start": "A", "end": "C", "max_depth": "4"})
        assert resp.status_code == 200
        assert b"Shortest path found" in resp.data
        assert b"2 hops" in resp.data

    @patch("app.find_path")
    @patch("app.path_with_urls")
    def test_api_path_returns_json(self, mock_pwu, mock_fp, client):
        mock_fp.return_value = ["A", "B"]
        mock_pwu.return_value = [
            {"title": "A", "url": "https://en.wikipedia.org/wiki/A"},
            {"title": "B", "url": "https://en.wikipedia.org/wiki/B"},
        ]
        resp = client.get("/api/path?start=A&end=B")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["hops"] == 1
        assert len(data["path"]) == 2

    def test_api_path_missing_params(self, client):
        resp = client.get("/api/path?start=A")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_api_path_invalid_max_depth(self, client):
        resp = client.get("/api/path?start=A&end=B&max_depth=abc")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "max_depth" in data["error"]

    @patch("app.find_path")
    def test_api_path_not_found(self, mock_fp, client):
        mock_fp.return_value = None
        resp = client.get("/api/path?start=A&end=B")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    @patch("app.find_path")
    def test_api_path_value_error(self, mock_fp, client):
        mock_fp.side_effect = ValueError("Article not found")
        resp = client.get("/api/path?start=Bad&end=B")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    @patch("app.find_path")
    def test_api_path_runtime_error(self, mock_fp, client):
        mock_fp.side_effect = RuntimeError("Wikipedia API failed")
        resp = client.get("/api/path?start=A&end=B")
        assert resp.status_code == 502
        assert "error" in resp.get_json()
        assert "Wikipedia" in resp.get_json()["error"]
