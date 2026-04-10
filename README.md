# 🏁 WikiRace Solver

A Python web application that finds the **shortest link path** between any two Wikipedia articles using **breadth-first search (BFS)** and the [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page).

> _"Six degrees of Wikipedia"_ — given any two articles, this tool discovers the fewest number of hyperlink hops needed to travel from one to the other.

## Features

- **BFS-based pathfinding** – guarantees the shortest path between two Wikipedia articles
- **Web interface** – clean, responsive UI to enter article titles or full Wikipedia URLs
- **JSON API** – programmatic access via a REST endpoint
- **Redirect resolution** – automatically follows Wikipedia redirects to canonical titles
- **Configurable depth limit** – control the maximum number of hops (default: 4)
- **Rate-limited requests** – polite API usage with configurable delays

## Project Structure

```
wikirace_solution/
├── app.py               # Flask web application (routes & API)
├── wikirace.py          # Core BFS solver & Wikipedia API helpers
├── requirements.txt     # Python dependencies
├── templates/
│   └── index.html       # Frontend UI template
└── tests/
    └── test_wikirace.py # Unit tests (mocked network calls)
```

## Getting Started

### Prerequisites

- Python 3.10+

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/evanyfc/wikirace_solution.git
   cd wikirace_solution
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS / Linux
   .venv\Scripts\activate      # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

```bash
python app.py
```

The server starts at **http://127.0.0.1:5000**. Open it in your browser, enter a start and end Wikipedia article, and click **Find shortest path**.

To enable debug mode:
```bash
FLASK_DEBUG=1 python app.py
```

## Usage

### Web Interface

1. Navigate to `http://127.0.0.1:5000`
2. Enter the **start** and **end** Wikipedia article titles (or full URLs)
3. Optionally adjust the **max hops** depth limit (1–6)
4. Click **Find shortest path**

### JSON API

**Endpoint:** `GET /api/path`

| Parameter   | Required | Default | Description                          |
|-------------|----------|---------|--------------------------------------|
| `start`     | Yes      | —       | Wikipedia article title or URL       |
| `end`       | Yes      | —       | Wikipedia article title or URL       |
| `max_depth` | No       | `4`     | Maximum number of hops to explore    |

**Example request:**
```bash
curl "http://127.0.0.1:5000/api/path?start=Albert+Einstein&end=Nuclear+weapon"
```

**Example response:**
```json
{
  "path": [
    {"title": "Albert Einstein", "url": "https://en.wikipedia.org/wiki/Albert_Einstein"},
    {"title": "Nuclear weapon", "url": "https://en.wikipedia.org/wiki/Nuclear_weapon"}
  ],
  "hops": 1
}
```

**Error responses** return an `error` field with an appropriate HTTP status code (`400`, `404`, or `502`).

## Running Tests

Tests use `pytest` with mocked network calls, so they run quickly and fully offline:

```bash
pytest
```

## Tech Stack

- **[Flask](https://flask.palletsprojects.com/)** – lightweight web framework
- **[Requests](https://docs.python-requests.org/)** – HTTP client for the MediaWiki API
- **[pytest](https://docs.pytest.org/)** – testing framework

## How It Works

1. **Title normalization** – Resolves user input (titles or URLs) to canonical Wikipedia article titles, following any redirects.
2. **BFS traversal** – Starting from the source article, the solver explores outgoing wiki-links level by level.
3. **Link extraction** – For each article, all article-namespace (`ns=0`) links are fetched via the MediaWiki API, with automatic pagination handling.
4. **Shortest path guarantee** – BFS explores nodes in order of distance, so the first path found to the target is always the shortest.
5. **Depth limiting** – Search is bounded by a configurable `max_depth` to prevent excessively long searches.
