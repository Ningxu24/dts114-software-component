from flask import Flask, jsonify, request, abort, render_template
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from typing import Any, Dict, List, Optional


app = Flask(__name__, template_folder="templates")
CORS(app)

# In-memory data store
books: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "The Night Circus",
        "author": "Erin Morgenstern",
        "genre": "Fantasy",
        "price": 14.99,
        "description": "A mysterious traveling circus appears without warning, opening only at night. Two young illusionists are bound to a magical competition with unknowable stakes.",
        "cover_url": "https://example.com/covers/the-night-circus.jpg",
    },
    {
        "id": 2,
        "title": "Sapiens: A Brief History of Humankind",
        "author": "Yuval Noah Harari",
        "genre": "Nonfiction",
        "price": 18.50,
        "description": "An accessible, sweeping history of Homo sapiens—how biology and history defined us, and how we can define the future.",
        "cover_url": "https://example.com/covers/sapiens.jpg",
    },
    {
        "id": 3,
        "title": "The Martian",
        "author": "Andy Weir",
        "genre": "Science Fiction",
        "price": 12.99,
        "description": "An astronaut is stranded on Mars and must use ingenuity, science, and sheer stubbornness to survive until rescue is possible.",
        "cover_url": "https://example.com/covers/the-martian.jpg",
    },
    {
        "id": 4,
        "title": "Where the Crawdads Sing",
        "author": "Delia Owens",
        "genre": "Mystery",
        "price": 16.25,
        "description": "In the marshes of North Carolina, a young woman grows up in isolation, becoming entangled in a small-town mystery and an unexpected love story.",
        "cover_url": "https://example.com/covers/where-the-crawdads-sing.jpg",
    },
    {
        "id": 5,
        "title": "Atomic Habits",
        "author": "James Clear",
        "genre": "Self-Help",
        "price": 17.00,
        "description": "A practical framework for building good habits, breaking bad ones, and making tiny changes that lead to remarkable results.",
        "cover_url": "https://example.com/covers/atomic-habits.jpg",
    },
    {
        "id": 6,
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "genre": "Classic",
        "price": 9.99,
        "description": "A witty, enduring romance exploring class, family, and first impressions through Elizabeth Bennet and Mr. Darcy.",
        "cover_url": "https://example.com/covers/pride-and-prejudice.jpg",
    },
]


def _next_id() -> int:
    if not books:
        return 1
    return max(b["id"] for b in books) + 1


def _get_book_or_404(book_id: int) -> Dict[str, Any]:
    for b in books:
        if b.get("id") == book_id:
            return b
    abort(404, description="Book not found")


def _as_non_empty_str(value: Any, field: str) -> str:
    if value is None:
        abort(400, description=f"Missing required field: {field}")
    if not isinstance(value, str):
        abort(400, description=f"Field '{field}' must be a string")
    v = value.strip()
    if not v:
        abort(400, description=f"Field '{field}' cannot be empty")
    return v


def _as_price(value: Any) -> float:
    if value is None:
        abort(400, description="Missing required field: price")
    try:
        p = float(value)
    except (TypeError, ValueError):
        abort(400, description="Field 'price' must be a number")
    if p < 0:
        abort(400, description="Field 'price' must be >= 0")
    return round(p, 2)


def _validate_cover_url(value: Any) -> str:
    url = _as_non_empty_str(value, "cover_url")
    if not (url.startswith("http://") or url.startswith("https://")):
        abort(400, description="Field 'cover_url' must start with http:// or https://")
    return url


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/books")
def list_books():
    genre = request.args.get("genre", type=str)
    search = request.args.get("search", type=str)

    results = books

    if genre:
        g = genre.strip().lower()
        results = [b for b in results if str(b.get("genre", "")).strip().lower() == g]

    if search:
        s = search.strip().lower()
        if s:
            results = [
                b
                for b in results
                if s in str(b.get("title", "")).lower()
                or s in str(b.get("author", "")).lower()
                or s in str(b.get("description", "")).lower()
            ]

    return jsonify(results), 200


@app.get("/api/books/<int:book_id>")
def get_book(book_id: int):
    book = _get_book_or_404(book_id)
    return jsonify(book), 200


@app.post("/api/books")
def add_book():
    if not request.is_json:
        abort(400, description="Request body must be JSON")

    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        abort(400, description="Invalid JSON body")

    title = _as_non_empty_str(data.get("title"), "title")
    author = _as_non_empty_str(data.get("author"), "author")
    genre = _as_non_empty_str(data.get("genre"), "genre")
    price = _as_price(data.get("price"))
    description = _as_non_empty_str(data.get("description"), "description")
    cover_url = _validate_cover_url(data.get("cover_url"))

    new_book = {
        "id": _next_id(),
        "title": title,
        "author": author,
        "genre": genre,
        "price": price,
        "description": description,
        "cover_url": cover_url,
    }
    books.append(new_book)
    return jsonify(new_book), 201


@app.get("/api/genres")
def list_genres():
    unique = sorted({str(b.get("genre", "")).strip() for b in books if str(b.get("genre", "")).strip()})
    return jsonify(unique), 200


@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    response = {
        "error": e.name,
        "message": e.description if isinstance(e.description, str) else "Request failed",
        "status": e.code,
    }
    return jsonify(response), e.code


@app.errorhandler(Exception)
def handle_unexpected_exception(e: Exception):
    response = {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "status": 500,
    }
    return jsonify(response), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)