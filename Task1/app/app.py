from flask import Flask, jsonify, request, abort, render_template
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
import re

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

books = [
    {
        "id": 1,
        "title": "The Night Circus",
        "author": "Erin Morgenstern",
        "genre": "Fantasy",
        "price": 14.99,
        "description": "A magical competition unfolds within a mysterious circus that appears without warning, enchanting all who enter.",
        "cover_url": "https://images.example.com/books/the-night-circus.jpg",
    },
    {
        "id": 2,
        "title": "The Martian",
        "author": "Andy Weir",
        "genre": "Science Fiction",
        "price": 12.50,
        "description": "An astronaut is stranded on Mars and must use ingenuity, science, and sheer will to survive until rescue is possible.",
        "cover_url": "https://images.example.com/books/the-martian.jpg",
    },
    {
        "id": 3,
        "title": "Educated",
        "author": "Tara Westover",
        "genre": "Memoir",
        "price": 13.99,
        "description": "A powerful memoir about growing up in a strict and isolated household and pursuing education against the odds.",
        "cover_url": "https://images.example.com/books/educated.jpg",
    },
    {
        "id": 4,
        "title": "The Silent Patient",
        "author": "Alex Michaelides",
        "genre": "Thriller",
        "price": 11.99,
        "description": "A psychotherapist becomes obsessed with unraveling why a famous painter stopped speaking after a shocking crime.",
        "cover_url": "https://images.example.com/books/the-silent-patient.jpg",
    },
    {
        "id": 5,
        "title": "Atomic Habits",
        "author": "James Clear",
        "genre": "Self-Help",
        "price": 16.00,
        "description": "A practical framework for building good habits, breaking bad ones, and making small changes that deliver remarkable results.",
        "cover_url": "https://images.example.com/books/atomic-habits.jpg",
    },
    {
        "id": 6,
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "genre": "Classic",
        "price": 9.99,
        "description": "A timeless romantic comedy of manners that follows Elizabeth Bennet as she navigates society, love, and misunderstanding.",
        "cover_url": "https://images.example.com/books/pride-and-prejudice.jpg",
    },
]


def _next_id() -> int:
    return (max((b["id"] for b in books), default=0) + 1) if books is not None else 1


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _validate_book_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        abort(400, description="Request body must be a JSON object.")

    required_fields = ["title", "author", "genre", "price", "description", "cover_url"]
    missing = [f for f in required_fields if f not in payload]
    if missing:
        abort(400, description=f"Missing required field(s): {', '.join(missing)}")

    title = str(payload.get("title", "")).strip()
    author = str(payload.get("author", "")).strip()
    genre = str(payload.get("genre", "")).strip()
    description = str(payload.get("description", "")).strip()
    cover_url = str(payload.get("cover_url", "")).strip()

    if not title:
        abort(400, description="Field 'title' must be a non-empty string.")
    if not author:
        abort(400, description="Field 'author' must be a non-empty string.")
    if not genre:
        abort(400, description="Field 'genre' must be a non-empty string.")
    if not description:
        abort(400, description="Field 'description' must be a non-empty string.")
    if not cover_url:
        abort(400, description="Field 'cover_url' must be a non-empty string.")

    price = payload.get("price")
    try:
        price = float(price)
    except (TypeError, ValueError):
        abort(400, description="Field 'price' must be a number.")
    if price < 0:
        abort(400, description="Field 'price' must be >= 0.")

    return {
        "title": title,
        "author": author,
        "genre": genre,
        "price": round(price, 2),
        "description": description,
        "cover_url": cover_url,
    }


@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    response = e.get_response()
    response.data = jsonify(
        {
            "error": e.name,
            "message": e.description,
            "status": e.code,
        }
    ).data
    response.content_type = "application/json"
    return response


@app.errorhandler(Exception)
def handle_unexpected_exception(e: Exception):
    return (
        jsonify(
            {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred.",
                "status": 500,
            }
        ),
        500,
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/books")
def list_books():
    genre = request.args.get("genre", default=None, type=str)
    search = request.args.get("search", default=None, type=str)

    results = books

    if genre:
        g = _normalize(genre)
        results = [b for b in results if _normalize(b.get("genre")) == g]

    if search:
        q = _normalize(search)
        results = [
            b
            for b in results
            if q in _normalize(b.get("title"))
            or q in _normalize(b.get("author"))
            or q in _normalize(b.get("genre"))
            or q in _normalize(b.get("description"))
        ]

    return jsonify(results)


@app.get("/api/books/<int:book_id>")
def get_book(book_id: int):
    book = next((b for b in books if b["id"] == book_id), None)
    if not book:
        abort(404, description="Book not found.")
    return jsonify(book)


@app.post("/api/books")
def add_book():
    payload = request.get_json(silent=True)
    if payload is None:
        abort(400, description="Invalid or missing JSON body.")

    validated = _validate_book_payload(payload)
    new_book = {"id": _next_id(), **validated}
    books.append(new_book)
    return jsonify(new_book), 201


@app.get("/api/genres")
def list_genres():
    genres = sorted({b.get("genre", "").strip() for b in books if b.get("genre")})
    return jsonify(genres)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)