import re
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

APP_VERSION = '2.4.0'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gerat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'gerat-crm-secret-2024'
db = SQLAlchemy(app)


# ── Models ──────────────────────────────────────────────────────────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='mechanic')
    display_name = db.Column(db.String(100))


class Brand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    models = db.relationship('CarModel', backref='brand', lazy=True, cascade='all, delete-orphan')


class CarModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'), nullable=False)
    services = db.relationship('Service', backref='model', lazy=True, cascade='all, delete-orphan')


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey('car_model.id'), nullable=False)


class GeneralService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    car_info = db.Column(db.String(300))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='client', lazy=True, foreign_keys='Order.client_id')


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    client_name = db.Column(db.String(200))
    car_info = db.Column(db.String(200))
    total = db.Column(db.Integer, default=0)
    items = db.Column(db.Text, default='[]')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProductCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    products = db.relationship('Product', backref='category', lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    barcode = db.Column(db.String(100))
    sell_price = db.Column(db.Integer, nullable=False, default=0)
    buy_price = db.Column(db.Integer, default=0)
    quantity = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=True)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    cashier_name = db.Column(db.String(100))
    client_name = db.Column(db.String(200))
    total = db.Column(db.Integer, default=0)
    items = db.Column(db.Text, default='[]')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Auth ─────────────────────────────────────────────────────────────────────────

def current_user():
    uid = session.get('user_id')
    return db.session.get(User, uid) if uid else None


def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if not session.get('user_id'):
            if request.is_json:
                return jsonify({'success': False, 'error': 'Не авторизовано'}), 401
            return redirect(url_for('login_page'))
        return f(*a, **kw)
    return dec


# ── Helpers ───────────────────────────────────────────────────────────────────────

def _ok(**kw):
    return jsonify({'success': True, **kw})


def _err(msg='Помилка'):
    return jsonify({'success': False, 'error': msg}), 400


def _get(model, pk):
    return db.session.get(model, pk)


# ── Auth routes ───────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if session.get('user_id'):
        u = current_user()
        return redirect(url_for('shop' if u and u.role == 'cashier' else 'index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        u = User.query.filter_by(username=username).first()
        if u and check_password_hash(u.password_hash, password):
            session['user_id'] = u.id
            return redirect(url_for('shop' if u.role == 'cashier' else 'index'))
        error = 'Невірний логін або пароль'
    return render_template('login.html', error=error, version=APP_VERSION)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ── Page routes ───────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    u = current_user()
    if u.role == 'cashier':
        return redirect(url_for('shop'))
    brands = Brand.query.all()
    db_dict = {}
    for b in brands:
        db_dict[b.name] = {}
        for m in b.models:
            db_dict[b.name][m.name] = [
                {'id': s.id, 'posluga': s.name, 'cina': s.price} for s in m.services
            ]
    gs_list = [{'id': s.id, 'posluga': s.name, 'cina': s.price}
               for s in GeneralService.query.all()]
    return render_template('index.html', db_dict=db_dict, general_services=gs_list,
                           version=APP_VERSION, user=u)


@app.route('/shop')
@login_required
def shop():
    u = current_user()
    if u.role == 'mechanic':
        return redirect(url_for('index'))
    cats = ProductCategory.query.order_by(ProductCategory.name).all()
    prods = Product.query.order_by(Product.name).all()
    return render_template('shop.html',
                           categories=[{'id': c.id, 'name': c.name} for c in cats],
                           products=[_product_dict(p) for p in prods],
                           version=APP_VERSION, user=u)


# ── User management (admin) ───────────────────────────────────────────────────────

@app.route('/api/users')
@login_required
def get_users():
    if current_user().role != 'admin':
        return _err('Немає прав'), 403
    return jsonify([_user_dict(u) for u in User.query.order_by(User.username)])


@app.route('/api/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user().role != 'admin':
        return _err('Немає прав'), 403
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    role = data.get('role') or 'mechanic'
    dname = (data.get('display_name') or '').strip()
    if not username:
        return _err('Введіть логін')
    if len(password) < 4:
        return _err('Пароль мінімум 4 символи')
    if role not in ('admin', 'mechanic', 'cashier'):
        return _err('Невірна роль')
    if User.query.filter_by(username=username).first():
        return _err('Такий логін вже існує')
    u = User(username=username,
             password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
             role=role, display_name=dname or None)
    db.session.add(u)
    db.session.commit()
    return _ok(user=_user_dict(u))


@app.route('/api/edit_user', methods=['POST'])
@login_required
def edit_user_route():
    if current_user().role != 'admin':
        return _err('Немає прав'), 403
    data = request.get_json() or {}
    u = _get(User, data.get('id'))
    if not u:
        return _err('Користувача не знайдено')
    role = data.get('role')
    if role and role in ('admin', 'mechanic', 'cashier'):
        u.role = role
    dname = (data.get('display_name') or '').strip()
    if dname:
        u.display_name = dname
    new_pass = data.get('password') or ''
    if new_pass:
        if len(new_pass) < 4:
            return _err('Пароль мінімум 4 символи')
        u.password_hash = generate_password_hash(new_pass, method='pbkdf2:sha256')
    db.session.commit()
    return _ok(user=_user_dict(u))


@app.route('/api/delete_user', methods=['POST'])
@login_required
def delete_user_route():
    me = current_user()
    if me.role != 'admin':
        return _err('Немає прав'), 403
    u = _get(User, (request.get_json() or {}).get('id'))
    if not u:
        return _err('Користувача не знайдено')
    if u.id == me.id:
        return _err('Не можна видалити себе')
    db.session.delete(u)
    db.session.commit()
    return _ok()


@app.route('/api/change_password', methods=['POST'])
@login_required
def change_password():
    me = current_user()
    data = request.get_json() or {}
    old_p = data.get('old_password') or ''
    new_p = data.get('new_password') or ''
    if len(new_p) < 4:
        return _err('Пароль мінімум 4 символи')
    if not check_password_hash(me.password_hash, old_p):
        return _err('Невірний поточний пароль')
    me.password_hash = generate_password_hash(new_p, method='pbkdf2:sha256')
    db.session.commit()
    return _ok()


# ── Shop: categories ──────────────────────────────────────────────────────────────

@app.route('/api/shop/add_category', methods=['POST'])
@login_required
def shop_add_cat():
    name = ((request.get_json() or {}).get('name') or '').strip()
    if not name:
        return _err('Введіть назву категорії')
    if ProductCategory.query.filter_by(name=name).first():
        return _err('Така категорія вже існує')
    c = ProductCategory(name=name)
    db.session.add(c)
    db.session.commit()
    return _ok(id=c.id, name=c.name)


@app.route('/api/shop/rename_category', methods=['POST'])
@login_required
def shop_rename_cat():
    data = request.get_json() or {}
    c = _get(ProductCategory, data.get('id'))
    if not c:
        return _err('Категорію не знайдено')
    name = (data.get('name') or '').strip()
    if not name:
        return _err('Введіть назву')
    c.name = name
    db.session.commit()
    return _ok(name=name)


@app.route('/api/shop/delete_category', methods=['POST'])
@login_required
def shop_del_cat():
    if current_user().role not in ('admin',):
        return _err('Немає прав'), 403
    c = _get(ProductCategory, (request.get_json() or {}).get('id'))
    if not c:
        return _err('Категорію не знайдено')
    Product.query.filter_by(category_id=c.id).update({'category_id': None})
    db.session.delete(c)
    db.session.commit()
    return _ok()


# ── Shop: products ────────────────────────────────────────────────────────────────

@app.route('/api/shop/add_product', methods=['POST'])
@login_required
def shop_add_prod():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return _err('Введіть назву товару')
    try:
        sp = int(data.get('sell_price', 0))
        bp = int(data.get('buy_price', 0))
        qty = int(data.get('quantity', 0))
        assert sp >= 0 and bp >= 0 and qty >= 0
    except Exception:
        return _err('Некоректні значення')
    p = Product(name=name,
                barcode=(data.get('barcode') or '').strip() or None,
                sell_price=sp, buy_price=bp, quantity=qty,
                category_id=data.get('category_id') or None)
    db.session.add(p)
    db.session.commit()
    return _ok(product=_product_dict(p))


@app.route('/api/shop/edit_product', methods=['POST'])
@login_required
def shop_edit_prod():
    data = request.get_json() or {}
    p = _get(Product, data.get('id'))
    if not p:
        return _err('Товар не знайдено')
    name = (data.get('name') or '').strip()
    if name:
        p.name = name
    try:
        if 'sell_price' in data:
            p.sell_price = int(data['sell_price']); assert p.sell_price >= 0
        if 'buy_price' in data:
            p.buy_price = int(data['buy_price']); assert p.buy_price >= 0
        if 'quantity' in data:
            p.quantity = int(data['quantity']); assert p.quantity >= 0
    except Exception:
        return _err('Некоректні значення')
    if 'barcode' in data:
        p.barcode = (data['barcode'] or '').strip() or None
    if 'category_id' in data:
        p.category_id = data['category_id'] or None
    db.session.commit()
    return _ok(product=_product_dict(p))


@app.route('/api/shop/delete_product', methods=['POST'])
@login_required
def shop_del_prod():
    if current_user().role not in ('admin',):
        return _err('Тільки адміністратор може видаляти товари'), 403
    p = _get(Product, (request.get_json() or {}).get('id'))
    if not p:
        return _err('Товар не знайдено')
    db.session.delete(p)
    db.session.commit()
    return _ok()


@app.route('/api/shop/adjust_stock', methods=['POST'])
@login_required
def shop_adjust_stock():
    data = request.get_json() or {}
    p = _get(Product, data.get('id'))
    if not p:
        return _err('Товар не знайдено')
    try:
        delta = int(data.get('delta', 0))
    except Exception:
        return _err('Некоректне значення')
    p.quantity = max(0, p.quantity + delta)
    db.session.commit()
    return _ok(quantity=p.quantity)


# ── Shop: sales ───────────────────────────────────────────────────────────────────

@app.route('/api/shop/sales')
@login_required
def shop_get_sales():
    return jsonify([_sale_dict(s) for s in Sale.query.order_by(Sale.created_at.desc()).limit(200)])


@app.route('/api/shop/save_sale', methods=['POST'])
@login_required
def shop_save_sale():
    u = current_user()
    data = request.get_json() or {}
    items_raw = data.get('items', '[]')
    total = int(data.get('total') or 0)
    try:
        items_list = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
    except Exception:
        items_list = []
    for item in items_list:
        pid = item.get('id')
        qty = int(item.get('qty', 1))
        if pid:
            p = _get(Product, pid)
            if p:
                p.quantity = max(0, p.quantity - qty)
    items_str = json.dumps(items_list, ensure_ascii=False)
    s = Sale(cashier_id=u.id,
             cashier_name=u.display_name or u.username,
             client_name=(data.get('client_name') or '').strip() or None,
             total=total,
             items=items_str,
             notes=(data.get('notes') or '').strip() or None)
    db.session.add(s)
    db.session.commit()
    return _ok(id=s.id)


@app.route('/api/shop/delete_sale', methods=['POST'])
@login_required
def shop_del_sale():
    if current_user().role != 'admin':
        return _err('Тільки адміністратор може видаляти продажі'), 403
    s = _get(Sale, (request.get_json() or {}).get('id'))
    if not s:
        return _err('Продаж не знайдено')
    db.session.delete(s)
    db.session.commit()
    return _ok()


# ── Stats ─────────────────────────────────────────────────────────────────────────

@app.route('/api/stats')
@login_required
def get_stats():
    from datetime import date as _date
    today_start = datetime.combine(_date.today(), datetime.min.time())
    crm_revenue  = db.session.query(db.func.sum(Order.total)).filter(Order.created_at >= today_start).scalar() or 0
    crm_orders   = Order.query.filter(Order.created_at >= today_start).count()
    shop_revenue = db.session.query(db.func.sum(Sale.total)).filter(Sale.created_at >= today_start).scalar() or 0
    shop_sales   = Sale.query.filter(Sale.created_at >= today_start).count()
    low_stock    = Product.query.filter(Product.quantity <= 3).count()
    out_of_stock = Product.query.filter(Product.quantity == 0).count()
    total_clients = Client.query.count()
    return jsonify({
        'crm_revenue': int(crm_revenue),
        'crm_orders': crm_orders,
        'shop_revenue': int(shop_revenue),
        'shop_sales': shop_sales,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'total_clients': total_clients,
    })


# ── CRM API ───────────────────────────────────────────────────────────────────────

@app.route('/api/get_data')
@login_required
def get_data():
    brands = Brand.query.all()
    db_dict = {}
    for b in brands:
        db_dict[b.name] = {}
        for m in b.models:
            db_dict[b.name][m.name] = [
                {'id': s.id, 'posluga': s.name, 'cina': s.price} for s in m.services
            ]
    gs_list = [{'id': s.id, 'posluga': s.name, 'cina': s.price}
               for s in GeneralService.query.all()]
    return jsonify({'db_dict': db_dict, 'general_services': gs_list})


@app.route('/api/add_car', methods=['POST'])
@login_required
def add_car():
    data = request.get_json() or {}
    b_name = (data.get('brand') or '').strip()
    m_name = (data.get('model') or '').strip()
    if not b_name:
        return _err('Введіть назву марки')
    brand = Brand.query.filter_by(name=b_name).first() or Brand(name=b_name)
    if not brand.id:
        db.session.add(brand)
        db.session.flush()
    if m_name and not CarModel.query.filter_by(name=m_name, brand_id=brand.id).first():
        db.session.add(CarModel(name=m_name, brand_id=brand.id))
    db.session.commit()
    return _ok()


@app.route('/api/rename_brand', methods=['POST'])
@login_required
def rename_brand():
    data = request.get_json() or {}
    new = (data.get('new_name') or '').strip()
    if not new:
        return _err('Нова назва порожня')
    brand = Brand.query.filter_by(name=data.get('old_name')).first()
    if not brand:
        return _err('Марку не знайдено')
    if Brand.query.filter_by(name=new).first():
        return _err('Така марка вже існує')
    brand.name = new
    db.session.commit()
    return _ok()


@app.route('/api/rename_model', methods=['POST'])
@login_required
def rename_model():
    data = request.get_json() or {}
    new = (data.get('new_name') or '').strip()
    if not new:
        return _err('Нова назва порожня')
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if not brand:
        return _err('Марку не знайдено')
    model = CarModel.query.filter_by(name=data.get('old_name'), brand_id=brand.id).first()
    if not model:
        return _err('Модель не знайдено')
    model.name = new
    db.session.commit()
    return _ok()


@app.route('/api/delete_brand', methods=['POST'])
@login_required
def delete_brand():
    brand = Brand.query.filter_by(name=(request.get_json() or {}).get('name')).first()
    if not brand:
        return _err('Марку не знайдено')
    db.session.delete(brand)
    db.session.commit()
    return _ok()


@app.route('/api/delete_model', methods=['POST'])
@login_required
def delete_model():
    data = request.get_json() or {}
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if not brand:
        return _err('Марку не знайдено')
    model = CarModel.query.filter_by(name=data.get('model'), brand_id=brand.id).first()
    if not model:
        return _err('Модель не знайдено')
    db.session.delete(model)
    db.session.commit()
    return _ok()


@app.route('/api/bulk_import', methods=['POST'])
@login_required
def bulk_import():
    text = (request.get_json() or {}).get('text', '')
    matches = re.findall(r'"([^"]+)"\s*\{([^}]+)\}\s*\[([^\]]+)\]\s*\|\s*(\d+)\s*\|', text)
    added = 0
    for b_raw, m_raw, s_raw, price in matches:
        b_name, m_name, s_name = b_raw.strip(), m_raw.strip(), s_raw.strip()
        brand = Brand.query.filter_by(name=b_name).first()
        if not brand:
            brand = Brand(name=b_name)
            db.session.add(brand)
            db.session.flush()
        model = CarModel.query.filter_by(name=m_name, brand_id=brand.id).first()
        if not model:
            model = CarModel(name=m_name, brand_id=brand.id)
            db.session.add(model)
            db.session.flush()
        if not Service.query.filter_by(name=s_name, model_id=model.id).first():
            db.session.add(Service(name=s_name, price=int(price), model_id=model.id))
            added += 1
    db.session.commit()
    return _ok(added=added)


@app.route('/api/add_service', methods=['POST'])
@login_required
def add_service():
    data = request.get_json() or {}
    name = (data.get('service_name') or '').strip()
    if not name:
        return _err('Введіть назву послуги')
    try:
        price = int(data.get('price', -1))
        assert price >= 0
    except Exception:
        return _err('Некоректна ціна')
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if not brand:
        return _err('Марку не знайдено')
    model = CarModel.query.filter_by(name=data.get('model'), brand_id=brand.id).first()
    if not model:
        return _err('Модель не знайдено')
    s = Service(name=name, price=price, model_id=model.id)
    db.session.add(s)
    db.session.commit()
    return _ok(id=s.id)


@app.route('/api/edit_service', methods=['POST'])
@login_required
def edit_service():
    data = request.get_json() or {}
    s = _get(Service, data.get('id'))
    if not s:
        return _err('Послугу не знайдено')
    new_name = (data.get('name') or '').strip()
    if new_name:
        s.name = new_name
    try:
        price = int(data.get('price', -1))
        assert price >= 0
        s.price = price
    except Exception:
        return _err('Некоректна ціна')
    db.session.commit()
    return _ok()


@app.route('/api/delete_service', methods=['POST'])
@login_required
def delete_service():
    s = _get(Service, (request.get_json() or {}).get('id'))
    if not s:
        return _err('Послугу не знайдено')
    db.session.delete(s)
    db.session.commit()
    return _ok()


@app.route('/api/add_general_service', methods=['POST'])
@login_required
def add_gen_service():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return _err('Введіть назву')
    try:
        price = int(data.get('price', -1))
        assert price >= 0
    except Exception:
        return _err('Некоректна ціна')
    s = GeneralService(name=name, price=price)
    db.session.add(s)
    db.session.commit()
    return _ok(id=s.id)


@app.route('/api/delete_general_service', methods=['POST'])
@login_required
def delete_gen_service():
    s = _get(GeneralService, (request.get_json() or {}).get('id'))
    if not s:
        return _err('Послугу не знайдено')
    db.session.delete(s)
    db.session.commit()
    return _ok()


@app.route('/api/orders')
@login_required
def get_orders():
    return jsonify([_order_dict(o)
                    for o in Order.query.order_by(Order.created_at.desc()).limit(200)])


@app.route('/api/save_order', methods=['POST'])
@login_required
def save_order():
    data = request.get_json() or {}
    client_id = data.get('client_id') or None
    client_name = (data.get('client_name') or '').strip() or None
    car_info = (data.get('car_info') or '').strip() or None
    if not client_id and client_name:
        cl = Client.query.filter(Client.name.ilike(client_name)).first()
        if cl:
            client_id = cl.id
            if not car_info:
                car_info = cl.car_info
    o = Order(client_id=client_id, client_name=client_name, car_info=car_info,
              total=int(data.get('total') or 0), items=data.get('items') or '[]',
              notes=(data.get('notes') or '').strip() or None)
    db.session.add(o)
    db.session.commit()
    return _ok(id=o.id)


@app.route('/api/edit_order', methods=['POST'])
@login_required
def edit_order():
    data = request.get_json() or {}
    o = _get(Order, data.get('id'))
    if not o:
        return _err('Замовлення не знайдено')
    new_name = (data.get('client_name') or '').strip()
    if new_name:
        o.client_name = new_name
    o.car_info = (data.get('car_info') or '').strip() or None
    o.notes = (data.get('notes') or '').strip() or None
    db.session.commit()
    return _ok()


@app.route('/api/delete_order', methods=['POST'])
@login_required
def delete_order():
    o = _get(Order, (request.get_json() or {}).get('id'))
    if not o:
        return _err('Замовлення не знайдено')
    db.session.delete(o)
    db.session.commit()
    return _ok()


@app.route('/api/clients')
@login_required
def get_clients():
    return jsonify([_client_dict(c) for c in Client.query.order_by(Client.name)])


@app.route('/api/client/<int:cid>')
@login_required
def get_client(cid):
    c = _get(Client, cid)
    if not c:
        return _err('Клієнта не знайдено'), 404
    data = _client_dict(c)
    data['orders'] = [_order_dict(o) for o in
                      Order.query.filter(Order.client_id == cid).order_by(Order.created_at.desc())]
    return jsonify(data)


@app.route('/api/add_client', methods=['POST'])
@login_required
def add_client():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return _err("Введіть ім'я клієнта")
    cl = Client(name=name,
                phone=(data.get('phone') or '').strip() or None,
                car_info=(data.get('car_info') or '').strip() or None,
                notes=(data.get('notes') or '').strip() or None)
    db.session.add(cl)
    db.session.commit()
    return _ok(id=cl.id)


@app.route('/api/edit_client', methods=['POST'])
@login_required
def edit_client():
    data = request.get_json() or {}
    cl = _get(Client, data.get('id'))
    if not cl:
        return _err('Клієнта не знайдено')
    new_name = (data.get('name') or '').strip()
    if new_name:
        cl.name = new_name
    cl.phone = (data.get('phone') or '').strip() or None
    cl.car_info = (data.get('car_info') or '').strip() or None
    cl.notes = (data.get('notes') or '').strip() or None
    db.session.commit()
    return _ok()


@app.route('/api/delete_client', methods=['POST'])
@login_required
def delete_client():
    cl = _get(Client, (request.get_json() or {}).get('id'))
    if not cl:
        return _err('Клієнта не знайдено')
    db.session.delete(cl)
    db.session.commit()
    return _ok()


# ── Dict helpers ───────────────────────────────────────────────────────────────────

def _order_dict(o):
    return {'id': o.id, 'client_id': o.client_id, 'client_name': o.client_name or '',
            'car_info': o.car_info or '', 'total': o.total or 0, 'items': o.items or '[]',
            'notes': o.notes or '', 'created_at': o.created_at.strftime('%d.%m.%Y %H:%M')}


def _client_dict(c):
    order_count = Order.query.filter(Order.client_id == c.id).count()
    total_spent = db.session.query(db.func.sum(Order.total)).filter(
        Order.client_id == c.id).scalar() or 0
    return {'id': c.id, 'name': c.name, 'phone': c.phone or '', 'car_info': c.car_info or '',
            'notes': c.notes or '', 'created_at': c.created_at.strftime('%d.%m.%Y'),
            'order_count': order_count, 'total_spent': int(total_spent)}


def _product_dict(p):
    return {'id': p.id, 'name': p.name, 'barcode': p.barcode or '',
            'sell_price': p.sell_price, 'buy_price': p.buy_price, 'quantity': p.quantity,
            'category_id': p.category_id, 'category_name': p.category.name if p.category else ''}


def _sale_dict(s):
    return {'id': s.id, 'cashier_name': s.cashier_name or '', 'client_name': s.client_name or '',
            'total': s.total or 0, 'items': s.items or '[]', 'notes': s.notes or '',
            'created_at': s.created_at.strftime('%d.%m.%Y %H:%M')}


def _user_dict(u):
    return {'id': u.id, 'username': u.username, 'display_name': u.display_name or '', 'role': u.role}


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.first():
            db.session.add(User(
                username='admin',
                password_hash=generate_password_hash('admin', method='pbkdf2:sha256'),
                role='admin',
                display_name='Адміністратор'
            ))
            db.session.commit()
            print('>>> Створено користувача: admin / admin  (змініть пароль!)')
    app.run(debug=True, host='0.0.0.0', port=5000)
