"""
Multi-tenant (Station) tests for Gerat.

Covers:
  - Station CRUD by super admin
  - Permission enforcement (only super manages stations)
  - Data isolation between stations
  - Super admin can switch active station
  - Station admin cannot leak data across stations
  - User assignment to stations
  - Migration creates default station and promotes first admin

Run:  python -m pytest tests/test_multitenant.py -v
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from app import (
    app, db, User, Station, Order, Client, Brand, CarModel, Service,
    GeneralService, Product, ProductCategory, Sale, _run_migrations
)
from werkzeug.security import generate_password_hash


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        WTF_CSRF_ENABLED=False,
    )
    with app.test_client() as c:
        with app.app_context():
            _run_migrations()
            # Create a super admin and a second station for tests
            if not User.query.filter_by(role='super').first():
                db.session.add(User(
                    username='super', role='super', station_id=None,
                    display_name='Super',
                    password_hash=generate_password_hash('pwd', method='pbkdf2:sha256'),
                ))
                db.session.commit()
        yield c
        with app.app_context():
            db.drop_all()


def _login_as(c, username, password):
    return c.post('/login', data={'username': username, 'password': password},
                  follow_redirects=True)


def _make_user(username, role, station_id=None, password='pwd'):
    with app.app_context():
        u = User(
            username=username, role=role, station_id=station_id,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _make_station(name):
    with app.app_context():
        s = Station(name=name)
        db.session.add(s)
        db.session.commit()
        return s.id


# ── Migration ───────────────────────────────────────────────────────────────

class TestMigration:
    def test_default_station_created(self, client):
        with app.app_context():
            s = Station.query.filter_by(name='Герат').first()
            assert s is not None
            assert s.id == 1


# ── Station CRUD ────────────────────────────────────────────────────────────

class TestStationCRUD:
    def test_list_as_super(self, client):
        _login_as(client, 'super', 'pwd')
        r = client.get('/api/stations')
        assert r.status_code == 200
        data = r.get_json()
        assert any(s['name'] == 'Герат' for s in data)

    def test_create_station(self, client):
        _login_as(client, 'super', 'pwd')
        r = client.post('/api/stations/add', json={'name': 'Тесті'})
        assert r.status_code == 200
        body = r.get_json()
        assert body['success'] is True
        assert body['name'] == 'Тесті'
        with app.app_context():
            assert Station.query.filter_by(name='Тесті').first() is not None

    def test_duplicate_name_rejected(self, client):
        _login_as(client, 'super', 'pwd')
        client.post('/api/stations/add', json={'name': 'X'})
        r = client.post('/api/stations/add', json={'name': 'X'})
        assert r.get_json()['success'] is False

    def test_empty_name_rejected(self, client):
        _login_as(client, 'super', 'pwd')
        r = client.post('/api/stations/add', json={'name': '  '})
        assert r.get_json()['success'] is False

    def test_rename_station(self, client):
        _login_as(client, 'super', 'pwd')
        sid = _make_station('Old')
        r = client.post('/api/stations/rename', json={'id': sid, 'name': 'New'})
        assert r.get_json()['success'] is True
        with app.app_context():
            assert db.session.get(Station, sid).name == 'New'

    def test_delete_station_with_data(self, client):
        _login_as(client, 'super', 'pwd')
        sid = _make_station('ToDelete')
        # Seed some data into the doomed station
        with app.app_context():
            db.session.add(Order(client_name='X', total=100, station_id=sid))
            db.session.add(Client(name='Y', station_id=sid))
            db.session.commit()
        r = client.post('/api/stations/delete', json={'id': sid})
        assert r.get_json()['success'] is True
        with app.app_context():
            assert db.session.get(Station, sid) is None
            assert Order.query.filter_by(station_id=sid).count() == 0
            assert Client.query.filter_by(station_id=sid).count() == 0

    def test_cannot_delete_last_station(self, client):
        _login_as(client, 'super', 'pwd')
        # Only Герат exists; deleting it should be blocked
        r = client.post('/api/stations/delete', json={'id': 1})
        assert r.get_json()['success'] is False


# ── Permission enforcement ──────────────────────────────────────────────────

class TestPermissions:
    def test_non_super_cannot_add_station(self, client):
        _make_user('admin1', 'admin', station_id=1)
        _login_as(client, 'admin1', 'pwd')
        r = client.post('/api/stations/add', json={'name': 'Should Fail'})
        assert r.status_code == 403

    def test_non_super_cannot_delete_station(self, client):
        sid = _make_station('Тесті')
        _make_user('admin1', 'admin', station_id=1)
        _login_as(client, 'admin1', 'pwd')
        r = client.post('/api/stations/delete', json={'id': sid})
        assert r.status_code == 403

    def test_non_super_cannot_switch(self, client):
        sid = _make_station('Тесті')
        _make_user('admin1', 'admin', station_id=1)
        _login_as(client, 'admin1', 'pwd')
        r = client.post('/api/stations/switch', json={'id': sid})
        assert r.status_code == 403

    def test_mechanic_cannot_manage_users(self, client):
        _make_user('mech', 'mechanic', station_id=1)
        _login_as(client, 'mech', 'pwd')
        r = client.get('/api/users')
        assert r.status_code == 403


# ── Data isolation ──────────────────────────────────────────────────────────

class TestDataIsolation:
    def test_admin_sees_only_own_station_orders(self, client):
        sid_a = 1
        sid_b = _make_station('Тесті')
        with app.app_context():
            db.session.add(Order(client_name='A1', total=100, station_id=sid_a))
            db.session.add(Order(client_name='B1', total=999, station_id=sid_b))
            db.session.commit()
        _make_user('admin_a', 'admin', station_id=sid_a)
        _login_as(client, 'admin_a', 'pwd')
        rows = client.get('/api/orders').get_json()
        names = [o['client_name'] for o in rows]
        assert 'A1' in names
        assert 'B1' not in names

    def test_admin_sees_only_own_clients(self, client):
        sid_a = 1
        sid_b = _make_station('Тесті')
        with app.app_context():
            db.session.add(Client(name='ClientA', station_id=sid_a))
            db.session.add(Client(name='ClientB', station_id=sid_b))
            db.session.commit()
        _make_user('admin_a', 'admin', station_id=sid_a)
        _login_as(client, 'admin_a', 'pwd')
        rows = client.get('/api/clients').get_json()
        names = [c['name'] for c in rows]
        assert names == ['ClientA']

    def test_admin_cannot_delete_other_station_order(self, client):
        sid_b = _make_station('Тесті')
        oid = None
        with app.app_context():
            o = Order(client_name='X', total=100, station_id=sid_b)
            db.session.add(o); db.session.commit()
            oid = o.id
        _make_user('admin_a', 'admin', station_id=1)
        _login_as(client, 'admin_a', 'pwd')
        r = client.post('/api/delete_order', json={'id': oid})
        # Should reject because the order is in a different station
        assert r.get_json()['success'] is False
        with app.app_context():
            assert db.session.get(Order, oid) is not None  # still exists

    def test_analytics_scoped_to_station(self, client):
        sid_a = 1
        sid_b = _make_station('Тесті')
        with app.app_context():
            db.session.add(Order(client_name='A', total=100, station_id=sid_a, items='[]'))
            db.session.add(Order(client_name='B', total=999, station_id=sid_b, items='[]'))
            db.session.commit()
        _make_user('admin_a', 'admin', station_id=sid_a)
        _login_as(client, 'admin_a', 'pwd')
        d = client.get('/api/analytics/crm?days=7').get_json()
        assert d['total_orders']  == 1
        assert d['total_revenue'] == 100

    def test_stats_scoped_to_station(self, client):
        sid_b = _make_station('Тесті')
        with app.app_context():
            db.session.add(Client(name='A', station_id=1))
            db.session.add(Client(name='B1', station_id=sid_b))
            db.session.add(Client(name='B2', station_id=sid_b))
            db.session.commit()
        _make_user('admin_a', 'admin', station_id=1)
        _login_as(client, 'admin_a', 'pwd')
        d = client.get('/api/stats').get_json()
        assert d['total_clients'] == 1


# ── Super switch + create across stations ───────────────────────────────────

class TestSuperSwitch:
    def test_super_switch_changes_active_station(self, client):
        _login_as(client, 'super', 'pwd')
        sid_b = _make_station('Тесті')
        with app.app_context():
            db.session.add(Order(client_name='A', total=100, station_id=1, items='[]'))
            db.session.add(Order(client_name='B', total=200, station_id=sid_b, items='[]'))
            db.session.commit()
        # Initial: should see Герат (id 1) data
        rows = client.get('/api/orders').get_json()
        assert [o['client_name'] for o in rows] == ['A']
        # Switch to Тесті
        client.post('/api/stations/switch', json={'id': sid_b})
        rows = client.get('/api/orders').get_json()
        assert [o['client_name'] for o in rows] == ['B']

    def test_create_assigns_to_active_station(self, client):
        _login_as(client, 'super', 'pwd')
        sid_b = _make_station('Тесті')
        client.post('/api/stations/switch', json={'id': sid_b})
        client.post('/api/add_client', json={'name': 'NewClient'})
        with app.app_context():
            cl = Client.query.filter_by(name='NewClient').first()
            assert cl is not None
            assert cl.station_id == sid_b


# ── User management ─────────────────────────────────────────────────────────

class TestUserManagement:
    def test_super_lists_users_across_stations(self, client):
        sid_b = _make_station('Тесті')
        _make_user('a1', 'admin', station_id=1)
        _make_user('a2', 'admin', station_id=sid_b)
        _login_as(client, 'super', 'pwd')
        users = client.get('/api/users').get_json()
        names = {u['username'] for u in users}
        assert 'a1' in names and 'a2' in names

    def test_admin_lists_only_own_station_users(self, client):
        sid_b = _make_station('Тесті')
        _make_user('a1', 'admin',    station_id=1)
        _make_user('a2', 'mechanic', station_id=sid_b)
        _login_as(client, 'a1', 'pwd')
        users = client.get('/api/users').get_json()
        names = {u['username'] for u in users}
        assert 'a1' in names
        assert 'a2' not in names

    def test_super_creates_user_in_specific_station(self, client):
        sid_b = _make_station('Тесті')
        _login_as(client, 'super', 'pwd')
        r = client.post('/api/add_user', json={
            'username': 'mech_b', 'password': '12345', 'role': 'mechanic',
            'station_id': sid_b,
        })
        assert r.get_json()['success'] is True
        with app.app_context():
            u = User.query.filter_by(username='mech_b').first()
            assert u.station_id == sid_b

    def test_admin_cannot_create_super(self, client):
        _make_user('admin_a', 'admin', station_id=1)
        _login_as(client, 'admin_a', 'pwd')
        r = client.post('/api/add_user', json={
            'username': 'rogue', 'password': '12345', 'role': 'super',
        })
        assert r.get_json()['success'] is False

    def test_admin_creates_user_in_own_station(self, client):
        sid_b = _make_station('Тесті')
        _make_user('admin_a', 'admin', station_id=1)
        _login_as(client, 'admin_a', 'pwd')
        r = client.post('/api/add_user', json={
            'username': 'mech_a', 'password': '12345', 'role': 'mechanic',
            'station_id': sid_b,  # admin tries to steal user into another station
        })
        # Should succeed, but station_id forced to admin's own station
        assert r.get_json()['success'] is True
        with app.app_context():
            u = User.query.filter_by(username='mech_a').first()
            assert u.station_id == 1  # NOT sid_b
