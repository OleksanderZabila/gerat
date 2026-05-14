"""
Analytics endpoint tests for Gerat Auto Service.
Covers:
  - Auth requirements
  - Period parameter parsing & clamping
  - Series shape (correct length, oldest first, gaps filled)
  - KPI math (totals, averages, comparison to previous period)
  - Top services / clients / products aggregation
  - Profit calculation (revenue - buy_price * qty)
  - Inventory summary

Run:  python -m pytest tests/test_analytics.py -v
"""
import os
import sys
import json
import pytest
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from app import app, db, User, Order, Sale, Product, ProductCategory
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
            db.create_all()
            if not User.query.first():
                db.session.add(User(
                    username='admin',
                    password_hash=generate_password_hash('admin', method='pbkdf2:sha256'),
                    role='admin',
                    display_name='Test Admin',
                ))
                db.session.commit()
        yield c
        with app.app_context():
            db.drop_all()


def _login(c, username='admin', password='admin'):
    return c.post('/login', data={'username': username, 'password': password},
                  follow_redirects=True)


def _seed_orders(specs):
    """specs: list of (days_ago, client_name, total, items_list)."""
    with app.app_context():
        for days_ago, name, total, items in specs:
            o = Order(
                client_name=name,
                car_info='Ford Focus',
                total=total,
                items=json.dumps(items, ensure_ascii=False),
                created_at=datetime.now() - timedelta(days=days_ago),
            )
            db.session.add(o)
        db.session.commit()


def _seed_sales(specs):
    """specs: list of (days_ago, total, items_list)."""
    with app.app_context():
        for days_ago, total, items in specs:
            s = Sale(
                cashier_name='admin',
                total=total,
                items=json.dumps(items, ensure_ascii=False),
                created_at=datetime.now() - timedelta(days=days_ago),
            )
            db.session.add(s)
        db.session.commit()


def _seed_products(specs):
    """specs: list of (name, sell_price, buy_price, qty). Returns mapping name -> id."""
    ids = {}
    with app.app_context():
        for name, sp, bp, q in specs:
            p = Product(name=name, sell_price=sp, buy_price=bp, quantity=q)
            db.session.add(p)
            db.session.flush()
            ids[name] = p.id
        db.session.commit()
    return ids


# ── Auth ─────────────────────────────────────────────────────────────────────

class TestAnalyticsAuth:
    def test_crm_requires_auth(self, client):
        r = client.get('/api/analytics/crm', follow_redirects=False)
        assert r.status_code in (302, 401)

    def test_shop_requires_auth(self, client):
        r = client.get('/api/analytics/shop', follow_redirects=False)
        assert r.status_code in (302, 401)


# ── Period parameter ────────────────────────────────────────────────────────

class TestPeriodParam:
    def test_default_is_7_days(self, client):
        _login(client)
        d = client.get('/api/analytics/crm').get_json()
        assert d['period_days'] == 7
        assert len(d['series']) == 7

    def test_custom_period(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=30').get_json()
        assert d['period_days'] == 30
        assert len(d['series']) == 30

    def test_clamped_min(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=0').get_json()
        assert d['period_days'] == 1

    def test_clamped_max(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=9999').get_json()
        assert d['period_days'] == 365

    def test_invalid_falls_back_to_default(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=abc').get_json()
        assert d['period_days'] == 7


# ── Series shape ────────────────────────────────────────────────────────────

class TestSeriesShape:
    def test_empty_series_is_all_zeros(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=7').get_json()
        assert len(d['series']) == 7
        assert all(p['count'] == 0 and p['revenue'] == 0 for p in d['series'])

    def test_series_oldest_first(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=5').get_json()
        dates = [p['date'] for p in d['series']]
        assert dates == sorted(dates)

    def test_series_last_entry_is_today(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=7').get_json()
        assert d['series'][-1]['date'] == date.today().isoformat()

    def test_gaps_filled_with_zeros(self, client):
        _login(client)
        # Only one order, 2 days ago
        _seed_orders([(2, 'Petro', 500, [{'name': 'Oil', 'price': 500}])])
        d = client.get('/api/analytics/crm?days=7').get_json()
        non_zero_days = [p for p in d['series'] if p['count'] > 0]
        assert len(non_zero_days) == 1
        assert non_zero_days[0]['revenue'] == 500


# ── CRM totals ──────────────────────────────────────────────────────────────

class TestCRMTotals:
    def test_total_orders_and_revenue(self, client):
        _login(client)
        _seed_orders([
            (0, 'Petro',  500, [{'name': 'Oil',  'price': 500}]),
            (1, 'Ivan',  1000, [{'name': 'Tire', 'price': 1000}]),
            (3, 'Petro',  300, [{'name': 'Oil',  'price': 300}]),
        ])
        d = client.get('/api/analytics/crm?days=7').get_json()
        assert d['total_orders']  == 3
        assert d['total_revenue'] == 1800
        assert d['avg_order']     == 600  # 1800 // 3

    def test_avg_order_is_zero_when_no_orders(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=7').get_json()
        assert d['avg_order'] == 0

    def test_orders_outside_period_excluded(self, client):
        _login(client)
        # one inside window, one outside
        _seed_orders([
            (1,   'A', 500, [{'name': 'X', 'price': 500}]),
            (100, 'B', 999, [{'name': 'Y', 'price': 999}]),
        ])
        d = client.get('/api/analytics/crm?days=7').get_json()
        assert d['total_orders']  == 1
        assert d['total_revenue'] == 500

    def test_previous_period_comparison(self, client):
        _login(client)
        # period = 7 days; current period spans days 0..6, previous spans 7..13
        _seed_orders([
            (1,  'A', 1000, []),  # current
            (10, 'B',  500, []),  # previous
        ])
        d = client.get('/api/analytics/crm?days=7').get_json()
        assert d['total_orders'] == 1
        assert d['prev_orders']  == 1
        assert d['total_revenue'] == 1000
        assert d['prev_revenue']  == 500


# ── CRM aggregations ────────────────────────────────────────────────────────

class TestCRMAggregations:
    def test_top_services_aggregation(self, client):
        _login(client)
        _seed_orders([
            (1, 'A', 800, [{'name': 'Oil',         'price': 500},
                           {'name': 'Filter',      'price': 300}]),
            (2, 'B', 600, [{'name': 'Oil',         'price': 600}]),
            (3, 'C', 200, [{'name': 'Diagnostic',  'price': 200}]),
        ])
        d = client.get('/api/analytics/crm?days=7').get_json()
        names = [s['name'] for s in d['top_services']]
        assert 'Oil' in names
        oil = next(s for s in d['top_services'] if s['name'] == 'Oil')
        assert oil['count']   == 2
        assert oil['revenue'] == 1100  # 500 + 600

    def test_top_clients_aggregation(self, client):
        _login(client)
        _seed_orders([
            (1, 'Petro', 500, []),
            (2, 'Petro', 700, []),
            (3, 'Ivan',  900, []),
        ])
        d = client.get('/api/analytics/crm?days=7').get_json()
        # Ivan should be first (900) then Petro (1200)
        assert d['top_clients'][0]['name']    == 'Petro'
        assert d['top_clients'][0]['revenue'] == 1200
        assert d['top_clients'][0]['orders']  == 2
        assert d['top_clients'][1]['name']    == 'Ivan'

    def test_anonymous_orders_skipped_in_top_clients(self, client):
        _login(client)
        _seed_orders([
            (1, 'Petro', 500, []),
            (1, None,    700, []),
            (1, '',      300, []),
        ])
        d = client.get('/api/analytics/crm?days=7').get_json()
        names = [c['name'] for c in d['top_clients']]
        assert names == ['Petro']

    def test_malformed_items_json_does_not_crash(self, client):
        _login(client)
        with app.app_context():
            db.session.add(Order(
                client_name='X', total=100, items='not-json',
                created_at=datetime.now() - timedelta(days=1),
            ))
            db.session.commit()
        r = client.get('/api/analytics/crm?days=7')
        assert r.status_code == 200
        d = r.get_json()
        assert d['total_orders']  == 1
        assert d['total_revenue'] == 100
        assert d['top_services']  == []  # nothing parsed


# ── Shop totals ─────────────────────────────────────────────────────────────

class TestShopTotals:
    def test_total_sales_and_revenue(self, client):
        _login(client)
        _seed_sales([
            (0, 500, [{'name': 'Filter', 'qty': 1, 'price': 500}]),
            (1, 1000, [{'name': 'Tire',   'qty': 2, 'price': 500}]),
        ])
        d = client.get('/api/analytics/shop?days=7').get_json()
        assert d['total_sales']   == 2
        assert d['total_revenue'] == 1500
        assert d['avg_sale']      == 750

    def test_profit_calculation(self, client):
        _login(client)
        ids = _seed_products([
            ('Oil',    500, 300, 10),   # margin: 200 per unit
            ('Filter', 200, 100,  5),   # margin: 100 per unit
        ])
        _seed_sales([
            (1, 700, [
                {'id': ids['Oil'],    'name': 'Oil',    'qty': 1, 'price': 500},
                {'id': ids['Filter'], 'name': 'Filter', 'qty': 1, 'price': 200},
            ]),
        ])
        d = client.get('/api/analytics/shop?days=7').get_json()
        # Revenue: 500 + 200 = 700; Cost: 300 + 100 = 400; Profit: 300
        assert d['total_revenue'] == 700
        assert d['total_profit']  == 300

    def test_top_products_sorted_by_revenue(self, client):
        _login(client)
        ids = _seed_products([
            ('Oil',    500, 0, 100),
            ('Filter', 200, 0, 100),
        ])
        _seed_sales([
            (1, 500,  [{'id': ids['Oil'],    'name': 'Oil',    'qty': 1, 'price': 500}]),
            (2, 600,  [{'id': ids['Filter'], 'name': 'Filter', 'qty': 3, 'price': 200}]),
        ])
        d = client.get('/api/analytics/shop?days=7').get_json()
        names = [p['name'] for p in d['top_products']]
        assert names[:2] == ['Filter', 'Oil']  # 600 > 500
        filter_row = d['top_products'][0]
        assert filter_row['qty']     == 3
        assert filter_row['revenue'] == 600

    def test_untracked_product_in_sale(self, client):
        """Sale items without product id (legacy / manual) still appear in top products."""
        _login(client)
        _seed_sales([
            (1, 100, [{'name': 'Manual item', 'qty': 1, 'price': 100}]),
        ])
        d = client.get('/api/analytics/shop?days=7').get_json()
        assert d['total_revenue'] == 100
        names = [p['name'] for p in d['top_products']]
        assert 'Manual item' in names

    def test_inventory_summary(self, client):
        _login(client)
        _seed_products([
            ('Out1',     100, 50, 0),   # out of stock
            ('Out2',     100, 50, 0),   # out of stock
            ('Low1',     100, 50, 2),   # low stock
            ('Stocked',  100, 50, 20),  # normal: 20 * 100 = 2000
        ])
        d = client.get('/api/analytics/shop?days=7').get_json()
        inv = d['inventory']
        assert inv['out_of_stock'] == 2
        assert inv['low_stock']    == 1
        # Stocked + Low1 contribute to value: 20*100 + 2*100 = 2200
        assert inv['inventory_value'] == 2200


# ── Response schema ─────────────────────────────────────────────────────────

class TestResponseSchema:
    def test_crm_response_has_all_keys(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=7').get_json()
        for key in ['period_days', 'total_orders', 'total_revenue', 'avg_order',
                    'prev_orders', 'prev_revenue', 'series',
                    'top_services', 'top_clients']:
            assert key in d, f'missing key: {key}'

    def test_shop_response_has_all_keys(self, client):
        _login(client)
        d = client.get('/api/analytics/shop?days=7').get_json()
        for key in ['period_days', 'total_sales', 'total_revenue', 'total_profit',
                    'avg_sale', 'prev_sales', 'prev_revenue', 'series',
                    'top_products', 'inventory']:
            assert key in d, f'missing key: {key}'
        for key in ['out_of_stock', 'low_stock', 'inventory_value']:
            assert key in d['inventory'], f'missing inventory key: {key}'

    def test_series_entry_shape(self, client):
        _login(client)
        d = client.get('/api/analytics/crm?days=3').get_json()
        for entry in d['series']:
            assert set(entry.keys()) == {'date', 'count', 'revenue'}
            assert isinstance(entry['count'], int)
            assert isinstance(entry['revenue'], int)
