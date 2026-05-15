from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from datetime import datetime, timezone
import threading
import time
import secrets

app = Flask(__name__, template_folder="templates")
CORS(app)

# -----------------------------
# In-memory datastore
# -----------------------------
_DATA_LOCK = threading.Lock()
_ITEMS = [
    {
        "id": 1,
        "title": "The Pragmatic Programmer",
        "genre": "Software Engineering",
        "price": 42.00,
        "description": "Classic guide to pragmatic thinking, craftsmanship, and maintainable software development.",
    },
    {
        "id": 2,
        "title": "Clean Code",
        "genre": "Software Engineering",
        "price": 39.50,
        "description": "Principles and practices for writing readable, robust, and maintainable codebases.",
    },
    {
        "id": 3,
        "title": "Dune",
        "genre": "Science Fiction",
        "price": 14.99,
        "description": "Epic science fiction saga of politics, ecology, and destiny on the desert planet Arrakis.",
    },
    {
        "id": 4,
        "title": "The Name of the Wind",
        "genre": "Fantasy",
        "price": 12.99,
        "description": "A gifted musician and magician recounts his life story, legend, and the cost of fame.",
    },
    {
        "id": 5,
        "title": "Sapiens: A Brief History of Humankind",
        "genre": "History",
        "price": 18.00,
        "description": "A sweeping narrative of human evolution, culture, and the forces that shaped modern society.",
    },
    {
        "id": 6,
        "title": "Atomic Habits",
        "genre": "Self-Help",
        "price": 16.00,
        "description": "A practical framework for building good habits, breaking bad ones, and mastering tiny behaviors.",
    },
]

_NEXT_ID = max(i["id"] for i in _ITEMS) + 1

# -----------------------------
# Minimal security controls
# (Optional API key enforcement via env/config could be added; kept simple for scope)
# -----------------------------
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_BUCKETS = {}  # key: ip -> {"window_start": epoch_seconds, "count": int}
RATE_LIMIT_PER_MINUTE = 120


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message, status_code=400, **extra):
    payload = {
        "error": {
            "message": message,
            "status": status_code,
        }
    }
    if extra:
        payload["error"].update(extra)
    response = jsonify(payload)
    response.status_code = status_code
    return response


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _rate_limit():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    ip = ip.split(",")[0].strip()
    now = int(time.time())
    window = now // 60  # 60s windows
    with _RATE_LIMIT_LOCK:
        entry = _RATE_BUCKETS.get(ip)
        if not entry or entry["window"] != window:
            _RATE_BUCKETS[ip] = {"window": window, "count": 1}
            return None
        entry["count"] += 1
        if entry["count"] > RATE_LIMIT_PER_MINUTE:
            return _error(
                "Rate limit exceeded",
                status_code=429,
                limit=RATE_LIMIT_PER_MINUTE,
                window_seconds=60,
            )
    return None


@app.before_request
def _before_request():
    # Basic, lightweight rate limiting for API routes
    if request.path.startswith("/api/"):
        rl = _rate_limit()
        if rl is not None:
            return rl
    return None


# -----------------------------
# Web route
# -----------------------------
@app.get("/")
def index():
    return render_template("index.html")


# -----------------------------
# API routes (versionless per requirement)
# -----------------------------
@app.get("/api/items")
def list_items():
    category = request.args.get("category", default=None, type=str)
    search = request.args.get("search", default=None, type=str)

    category_n = _normalize(category) if category else None
    search_n = _normalize(search) if search else None

    with _DATA_LOCK:
        results = list(_ITEMS)

    if category_n:
        results = [i for i in results if _normalize(i.get("genre")) == category_n]

    if search_n:
        results = [
            i
            for i in results
            if search_n in _normalize(i.get("title")) or search_n in _normalize(i.get("description"))
        ]

    return jsonify(
        {
            "items": results,
            "count": len(results),
            "timestamp": _now_utc_iso(),
        }
    )


@app.get("/api/items/<int:item_id>")
def get_item(item_id: int):
    with _DATA_LOCK:
        item = next((i for i in _ITEMS if i["id"] == item_id), None)
    if not item:
        return _error("Item not found", status_code=404, id=item_id)
    return jsonify(item)


def _validate_item_payload(payload, require_all_fields: bool = True):
    if not isinstance(payload, dict):
        return "Invalid JSON body; expected an object"

    missing = []
    for field in ("title", "genre", "price", "description"):
        if field not in payload:
            missing.append(field)

    if require_all_fields and missing:
        return f"Missing required field(s): {', '.join(missing)}"

    if "title" in payload:
        if not isinstance(payload["title"], str) or not payload["title"].strip():
            return "Field 'title' must be a non-empty string"
    if "genre" in payload:
        if not isinstance(payload["genre"], str) or not payload["genre"].strip():
            return "Field 'genre' must be a non-empty string"
    if "description" in payload:
        if not isinstance(payload["description"], str) or not payload["description"].strip():
            return "Field 'description' must be a non-empty string"
    if "price" in payload:
        if not isinstance(payload["price"], (int, float)) or payload["price"] < 0:
            return "Field 'price' must be a non-negative number"

    return None


def _is_duplicate(title: str, genre: str):
    t = _normalize(title)
    g = _normalize(genre)
    with _DATA_LOCK:
        for it in _ITEMS:
            if _normalize(it.get("title")) == t and _normalize(it.get("genre")) == g:
                return it
    return None


@app.post("/api/items")
def add_item():
    if not request.is_json:
        return _error("Content-Type must be application/json", status_code=400)

    payload = request.get_json(silent=True)
    err = _validate_item_payload(payload, require_all_fields=True)
    if err:
        return _error(err, status_code=400)

    title = payload["title"].strip()
    genre = payload["genre"].strip()
    description = payload["description"].strip()
    price = float(payload["price"])

    dup = _is_duplicate(title, genre)
    if dup:
        return _error(
            "Duplicate item detected (same title and category)",
            status_code=400,
            duplicate_id=dup["id"],
        )

    global _NEXT_ID
    with _DATA_LOCK:
        item_id = _NEXT_ID
        _NEXT_ID += 1
        item = {
            "id": item_id,
            "title": title,
            "genre": genre,
            "price": round(price, 2),
            "description": description,
        }
        _ITEMS.append(item)

    resp = jsonify(item)
    resp.status_code = 201
    resp.headers["Location"] = f"/api/items/{item_id}"
    return resp


@app.get("/api/categories")
def list_categories():
    with _DATA_LOCK:
        genres = sorted({i.get("genre", "").strip() for i in _ITEMS if i.get("genre")})
    return jsonify({"categories": genres, "count": len(genres), "timestamp": _now_utc_iso()})


# -----------------------------
# Error handling
# -----------------------------
@app.errorhandler(404)
def handle_404(_e):
    return _error("Not found", status_code=404, path=request.path)


@app.errorhandler(400)
def handle_400(e):
    if isinstance(e, HTTPException) and e.description:
        return _error(e.description, status_code=400)
    return _error("Bad request", status_code=400)


@app.errorhandler(405)
def handle_405(_e):
    return _error("Method not allowed", status_code=405, path=request.path, method=request.method)


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return _error(e.description or "HTTP error", status_code=e.code or 500)
    request_id = secrets.token_hex(8)
    return _error("Internal server error", status_code=500, request_id=request_id)


if __name__ == "__main__":
    # Production: run behind a WSGI server (gunicorn/uwsgi). This is for local/dev.
    app.run(host="0.0.0.0", port=5000, debug=False)