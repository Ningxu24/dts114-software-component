from __future__ import annotations

import os
import time
import uuid
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from functools import wraps

from flask import Flask, jsonify, request, render_template, g
from flask_cors import CORS

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------

app = Flask(__name__, template_folder="templates")
CORS(app)

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bookstore-api")

# ------------------------------------------------------------------------------
# In-memory datastore
# ------------------------------------------------------------------------------

# Each item must have: id, name/title, category/genre, price, description
# We'll use: id, title, genre, price, description, plus extra metadata.
items: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "The Pragmatic Programmer: Your Journey to Mastery",
        "genre": "Technology",
        "authors": ["Andrew Hunt", "David Thomas"],
        "isbn": "978-0135957059",
        "price": 42.99,
        "availability": "in_stock",
        "description": "A modern software engineering classic with practical advice for building better systems and careers.",
        "published_year": 2019,
    },
    {
        "id": 2,
        "title": "Project Hail Mary",
        "genre": "Science Fiction",
        "authors": ["Andy Weir"],
        "isbn": "978-0593135204",
        "price": 16.99,
        "availability": "in_stock",
        "description": "A lone astronaut must save humanity in a high-stakes, science-driven adventure.",
        "published_year": 2021,
    },
    {
        "id": 3,
        "title": "Educated",
        "genre": "Memoir",
        "authors": ["Tara Westover"],
        "isbn": "978-0399590504",
        "price": 14.50,
        "availability": "low_stock",
        "description": "A memoir about family, resilience, and the transformative power of education.",
        "published_year": 2018,
    },
    {
        "id": 4,
        "title": "Atomic Habits",
        "genre": "Self-Help",
        "authors": ["James Clear"],
        "isbn": "978-0735211292",
        "price": 11.89,
        "availability": "in_stock",
        "description": "A practical framework for building good habits, breaking bad ones, and mastering tiny behaviors that lead to big results.",
        "published_year": 2018,
    },
    {
        "id": 5,
        "title": "The Name of the Wind",
        "genre": "Fantasy",
        "authors": ["Patrick Rothfuss"],
        "isbn": "978-0756404741",
        "price": 9.99,
        "availability": "out_of_stock",
        "description": "The riveting first-person tale of a legendary magician, musician, and rogue, recounting his extraordinary life.",
        "published_year": 2007,
    },
    {
        "id": 6,
        "title": "Sapiens: A Brief History of Humankind",
        "genre": "History",
        "authors": ["Yuval Noah Harari"],
        "isbn": "978-0062316097",
        "price": 18.00,
        "availability": "in_stock",
        "description": "A sweeping narrative of human history, from ancient ancestors to modern societies and the forces that shaped them.",
        "published_year": 2015,
    },
]

# ------------------------------------------------------------------------------
# Simple API auth (API key) and rate limiting
# ------------------------------------------------------------------------------

API_KEY_ENV = os.getenv("API_KEY", "").strip()
# If not provided, generate a stable-looking key per process (for dev/testing).
if not API_KEY_ENV:
    API_KEY_ENV = f"dev_{uuid.uuid4().hex}"
    logger.warning("API_KEY not set; using generated dev key: %s", API_KEY_ENV)

API_KEY_HEADER = os.getenv("API_KEY_HEADER", "X-API-Key")
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))  # per api key per minute
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "true").lower() in ("1", "true", "yes", "y")

_rate_buckets: Dict[str, Dict[str, Any]] = {}  # key -> {window_start, count}


def _get_client_api_key() -> Optional[str]:
    key = request.headers.get(API_KEY_HEADER) or request.args.get("api_key")
    if key:
        return key.strip()
    return None


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Only apply to /api routes
        if not request.path.startswith("/api/"):
            return fn(*args, **kwargs)

        if not ENABLE_AUTH:
            g.api_key = "auth_disabled"
            return fn(*args, **kwargs)

        provided = _get_client_api_key()
        if not provided or provided != API_KEY_ENV:
            return error_response(
                401,
                "unauthorized",
                f"Missing or invalid API key. Provide header {API_KEY_HEADER}.",
            )
        g.api_key = provided
        return fn(*args, **kwargs)

    return wrapper


def rate_limit(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not request.path.startswith("/api/"):
            return fn(*args, **kwargs)

        key = getattr(g, "api_key", None) or _get_client_api_key() or "anonymous"
        now = int(time.time())
        window = now - (now % 60)

        bucket = _rate_buckets.get(key)
        if not bucket or bucket["window_start"] != window:
            bucket = {"window_start": window, "count": 0}
            _rate_buckets[key] = bucket

        if bucket["count"] >= RATE_LIMIT_PER_MIN:
            resp = error_response(
                429,
                "rate_limited",
                "Rate limit exceeded. Please retry later.",
            )
            resp.headers["Retry-After"] = str(60 - (now - window))
            return resp

        bucket["count"] += 1
        return fn(*args, **kwargs)

    return wrapper


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

@dataclass
class ValidationError(Exception):
    message: str
    field: Optional[str] = None


def error_response(status_code: int, code: str, message: str, details: Optional[Dict[str, Any]] = None):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    resp = jsonify(payload)
    resp.status_code = status_code
    return resp


def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def parse_int(value: Optional[str], default: int, min_value: int, max_value: int) -> int:
    if value is None or value == "":
        return default
    try:
        i = int(value)
    except ValueError as e:
        raise ValidationError("Must be an integer.") from e
    if i < min_value or i > max_value:
        raise ValidationError(f"Must be between {min_value} and {max_value}.")
    return i


def parse_price(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError) as e:
        raise ValidationError("Price must be a number.", "price") from e
    if f < 0:
        raise ValidationError("Price must be >= 0.", "price")
    return round(f, 2)


def get_next_id() -> int:
    return (max((it["id"] for it in items), default=0) + 1)


def validate_new_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("JSON body must be an object.")

    # Accept either "name" or "title"
    title = payload.get("title", payload.get("name"))
    if title is None or not isinstance(title, str) or not title.strip():
        raise ValidationError("Field is required and must be a non-empty string.", "title")

    # Accept either "category" or "genre"
    genre = payload.get("genre", payload.get("category"))
    if genre is None or not isinstance(genre, str) or not genre.strip():
        raise ValidationError("Field is required and must be a non-empty string.", "genre")

    description = payload.get("description")
    if description is None or not isinstance(description, str) or not description.strip():
        raise ValidationError("Field is required and must be a non-empty string.", "description")

    price = parse_price(payload.get("price"))

    authors = payload.get("authors")
    if authors is None:
        authors = payload.get("author")  # allow single
        if isinstance(authors, str) and authors.strip():
            authors = [authors.strip()]
    if authors is not None and not (isinstance(authors, list) and all(isinstance(a, str) and a.strip() for a in authors)):
        raise ValidationError("If provided, authors must be a list of non-empty strings.", "authors")

    isbn = payload.get("isbn")
    if isbn is not None and (not isinstance(isbn, str) or not isbn.strip()):
        raise ValidationError("If provided, isbn must be a non-empty string.", "isbn")

    availability = payload.get("availability", "in_stock")
    if availability is not None:
        if not isinstance(availability, str):
            raise ValidationError("If provided, availability must be a string.", "availability")
        availability = availability.strip().lower()
        allowed = {"in_stock", "out_of_stock", "low_stock", "preorder"}
        if availability not in allowed:
            raise ValidationError(f"Availability must be one of: {sorted(allowed)}.", "availability")

    published_year = payload.get("published_year")
    if published_year is not None:
        if isinstance(published_year, str) and published_year.strip().isdigit():
            published_year = int(published_year.strip())
        if not isinstance(published_year, int) or published_year < 1400 or published_year > 2100:
            raise ValidationError("If provided, published_year must be a valid year.", "published_year")

    return {
        "id": get_next_id(),
        "title": title.strip(),
        "genre": genre.strip(),
        "price": price,
        "description": description.strip(),
        "authors": authors if authors is not None else [],
        "isbn": isbn.strip() if isinstance(isbn, str) else None,
        "availability": availability,
        "published_year": published_year,
    }


def filter_items(category: Optional[str], search: Optional[str]) -> List[Dict[str, Any]]:
    category_norm = normalize_text(category) if category else None
    search_norm = normalize_text(search) if search else None

    result = items

    if category_norm:
        result = [it for it in result if normalize_text(it.get("genre", "")) == category_norm]

    if search_norm:
        def matches(it: Dict[str, Any]) -> bool:
            hay = " ".join(
                [
                    str(it.get("title", "")),
                    str(it.get("description", "")),
                    " ".join(it.get("authors", []) or []),
                    str(it.get("genre", "")),
                    str(it.get("isbn", "") or ""),
                ]
            )
            return search_norm in normalize_text(hay)

        result = [it for it in result if matches(it)]

    return result


def paginate(rows: List[Dict[str, Any]], page: int, per_page: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    total = len(rows)
    start = (page - 1) * per_page
    end = start + per_page
    sliced = rows[start:end]
    meta = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page if per_page else 0,
        "has_next": end < total,
        "has_prev": start > 0,
    }
    return sliced, meta


# ------------------------------------------------------------------------------
# Request hooks (basic observability)
# ------------------------------------------------------------------------------

@app.before_request
def _before_request():
    g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    g.start_time = time.time()


@app.after_request
def _after_request(response):
    duration_ms = int((time.time() - getattr(g, "start_time", time.time())) * 1000)
    response.headers["X-Request-Id"] = getattr(g, "request_id", "")
    response.headers["X-Response-Time-ms"] = str(duration_ms)
    return response


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@app.get("/")
def index():
    # Requires templates/index.html to exist.
    return render_template("index.html")


@app.get("/api/categories")
@require_api_key
@rate_limit
def list_categories():
    cats = sorted({it.get("genre", "").strip() for it in items if it.get("genre")})
    return jsonify({"data": cats})


@app.get("/api/items")
@require_api_key
@rate_limit
def list_items():
    category = request.args.get("category")
    search = request.args.get("search")

    try:
        page = parse_int(request.args.get("page"), default=1, min_value=1, max_value=10_000)
        per_page = parse_int(request.args.get("per_page"), default=20, min_value=1, max_value=200)
    except ValidationError as ve:
        return error_response(400, "bad_request", ve.message, {"field": ve.field} if ve.field else None)

    # Optional sorting
    sort = (request.args.get("sort") or "").strip().lower()
    sort_dir = (request.args.get("dir") or "asc").strip().lower()
    if sort_dir not in ("asc", "desc"):
        return error_response(400, "bad_request", "dir must be 'asc' or 'desc'.")

    rows = filter_items(category, search)

    if sort:
        reverse = (sort_dir == "desc")

        def sort_key(it: Dict[str, Any]):
            if sort in ("title", "name"):
                return normalize_text(it.get("title", ""))
            if sort in ("price",):
                return it.get("price", 0.0)
            if sort in ("year", "published_year"):
                return it.get("published_year") or 0
            if sort in ("genre", "category"):
                return normalize_text(it.get("genre", ""))
            return None

        key = sort_key(rows[0]) if rows else None
        if key is None and sort not in ("title", "name", "price", "year", "published_year", "genre", "category"):
            return error_response(400, "bad_request", "Unsupported sort field.")
        rows = sorted(rows, key=sort_key, reverse=reverse)

    sliced, meta = paginate(rows, page, per_page)
    return jsonify({"data": sliced, "meta": meta})


@app.get("/api/items/<int:item_id>")
@require_api_key
@rate_limit
def get_item(item_id: int):
    it = next((x for x in items if x.get("id") == item_id), None)
    if not it:
        return error_response(404, "not_found", "Item not found.")
    return jsonify({"data": it})


@app.post("/api/items")
@require_api_key
@rate_limit
def add_item():
    if not request.is_json:
        return error_response(400, "bad_request", "Content-Type must be application/json.")
    payload = request.get_json(silent=True)
    if payload is None:
        return error_response(400, "bad_request", "Invalid JSON body.")

    try:
        new_item = validate_new_item(payload)
    except ValidationError as ve:
        details = {"field": ve.field} if ve.field else None
        return error_response(400, "bad_request", ve.message, details)

    # Ensure ISBN uniqueness if provided
    isbn = new_item.get("isbn")
    if isbn:
        existing = next((x for x in items if (x.get("isbn") or "").strip() == isbn), None)
        if existing:
            return error_response(400, "bad_request", "isbn must be unique.", {"field": "isbn"})

    items.append(new_item)
    resp = jsonify({"data": new_item})
    resp.status_code = 201
    return resp


# ------------------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------------------

@app.errorhandler(404)
def handle_404(_err):
    return error_response(404, "not_found", "Route not found.")


@app.errorhandler(405)
def handle_405(_err):
    return error_response(405, "method_not_allowed", "Method not allowed.")


@app.errorhandler(400)
def handle_400(_err):
    return error_response(400, "bad_request", "Bad request.")


@app.errorhandler(500)
def handle_500(err):
    logger.exception("Unhandled error: %s", err)
    return error_response(500, "internal_error", "An internal error occurred.")


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes", "y")
    app.run(host=host, port=port, debug=debug)