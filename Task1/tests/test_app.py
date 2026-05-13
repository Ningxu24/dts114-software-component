import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


def test_get_books(client):
    resp = client.get('/api/books')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_book_by_id(client):
    resp = client.get('/api/books/1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'title' in data


def test_get_book_not_found(client):
    resp = client.get('/api/books/9999')
    assert resp.status_code == 404


def test_get_genres(client):
    resp = client.get('/api/genres')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)


def test_home_page(client):
    resp = client.get('/')
    assert resp.status_code == 200
