"""
Basic smoke tests for Gerat Auto Service.
Run with: python -m pytest tests/ -v
"""
import os
import sys
import pytest

# Make sure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from app import app, db, User
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """Flask test client with an in-memory DB seeded with an admin user."""
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        WTF_CSRF_ENABLED=False,
    )
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            if not User.query.first():
                db.session.add(User(
                    username='admin',
                    password_hash=generate_password_hash('admin', method='pbkdf2:sha256'),
                    role='admin',
                    display_name='Test Admin',
                ))
                db.session.commit()
        yield client
        with app.app_context():
            db.drop_all()


def _login(client, username='admin', password='admin'):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_login_page_loads(self, client):
        """GET /login returns 200."""
        r = client.get('/login')
        assert r.status_code == 200

    def test_login_success(self, client):
        """Correct credentials redirect to home."""
        r = _login(client)
        assert r.status_code == 200
        assert b'login' not in r.request.path.lower().encode()

    def test_login_wrong_password(self, client):
        """Wrong password stays on login page."""
        r = client.post('/login', data={'username': 'admin', 'password': 'wrong'},
                        follow_redirects=True)
        assert r.status_code == 200
        # should still be on login page (or contain error)
        assert b'login' in r.request.path.lower().encode() or b'invalid' in r.data.lower()

    def test_unauthenticated_redirect(self, client):
        """Root redirects to /login when not logged in."""
        r = client.get('/', follow_redirects=False)
        assert r.status_code in (301, 302)
        assert '/login' in r.headers.get('Location', '')

    def test_logout(self, client):
        """Logout redirects to /login."""
        _login(client)
        r = client.get('/logout', follow_redirects=False)
        assert r.status_code in (301, 302)
        assert '/login' in r.headers.get('Location', '')


# ── Pages ─────────────────────────────────────────────────────────────────────

class TestPages:
    def test_index_loads_after_login(self, client):
        """/ loads for logged-in admin."""
        _login(client)
        r = client.get('/')
        assert r.status_code == 200

    def test_shop_loads_after_login(self, client):
        """/shop loads for logged-in admin."""
        _login(client)
        r = client.get('/shop')
        assert r.status_code == 200

    def test_404_returns_404(self, client):
        """Unknown route returns 404."""
        _login(client)
        r = client.get('/this-does-not-exist')
        assert r.status_code == 404


# ── API smoke tests ───────────────────────────────────────────────────────────

class TestAPI:
    def test_api_get_data(self, client):
        """/api/get_data returns a dict with brand data."""
        _login(client)
        r = client.get('/api/get_data')
        assert r.status_code == 200
        assert r.is_json
        assert isinstance(r.get_json(), dict)

    def test_api_requires_auth(self, client):
        """/api/get_data returns 302 when not logged in."""
        r = client.get('/api/get_data', follow_redirects=False)
        assert r.status_code in (302, 401)

    def test_api_stats(self, client):
        """/api/stats returns expected keys."""
        _login(client)
        r = client.get('/api/stats')
        assert r.status_code == 200
        data = r.get_json()
        assert 'crm_orders' in data
        assert 'total_clients' in data
        assert 'crm_revenue' in data
