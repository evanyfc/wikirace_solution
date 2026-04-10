"""
app.py – Flask web application for the WikiRace solver.

Routes
------
GET  /          – Render the search form.
POST /search    – Run the BFS solver and display the result.
GET  /api/path  – JSON API: ?start=<title>&end=<title>[&max_depth=<int>]
"""

from __future__ import annotations

import os

from flask import Flask, render_template, request, jsonify

from wikirace import find_path, path_with_urls

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    start = request.form.get("start", "").strip()
    end = request.form.get("end", "").strip()
    try:
        max_depth = int(request.form.get("max_depth", 4))
    except (ValueError, TypeError):
        max_depth = 4

    error = None
    result = None

    if not start or not end:
        error = "Please enter both a start and an end article."
    else:
        try:
            path = find_path(start, end, max_depth=max_depth)
            if path is None:
                error = (
                    f"No path found between '{start}' and '{end}' "
                    f"within {max_depth} hops. Try increasing the depth limit."
                )
            else:
                result = {
                    "path": path_with_urls(path),
                    "hops": len(path) - 1,
                }
        except ValueError as exc:
            error = str(exc)
        except RuntimeError:
            error = "An error occurred while contacting Wikipedia. Please try again later."

    return render_template("index.html", result=result, error=error, start=start, end=end)


@app.route("/api/path", methods=["GET"])
def api_path():
    """
    JSON API endpoint.

    Query params
    ------------
    start     : Wikipedia article title or URL (required)
    end       : Wikipedia article title or URL (required)
    max_depth : Maximum BFS depth (optional, default 4)

    Returns
    -------
    {
        "path": [{"title": "...", "url": "..."}, ...],
        "hops": <int>
    }
    or
    {
        "error": "..."
    }
    """
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    try:
        max_depth = int(request.args.get("max_depth", 4))
    except (ValueError, TypeError):
        return jsonify({"error": "max_depth must be an integer."}), 400

    if not start or not end:
        return jsonify({"error": "Both 'start' and 'end' query parameters are required."}), 400

    try:
        path = find_path(start, end, max_depth=max_depth)
    except ValueError:
        return jsonify({"error": "One or more Wikipedia articles could not be found."}), 404
    except RuntimeError:
        return jsonify({"error": "An error occurred while contacting Wikipedia. Please try again later."}), 502

    if path is None:
        return jsonify(
            {
                "error": (
                    f"No path found between '{start}' and '{end}' "
                    f"within {max_depth} hops."
                )
            }
        ), 404

    return jsonify({"path": path_with_urls(path), "hops": len(path) - 1})


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)
