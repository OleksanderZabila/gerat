import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

APP_VERSION = '2.2.0'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gerat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


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


def _ok(**kw):
    return jsonify({'success': True, **kw})


def _err(msg='Помилка'):
    return jsonify({'success': False, 'error': msg}), 400


def _get(model, pk):
    return db.session.get(model, pk)


# ─── Page ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
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
    return render_template('index.html', db_dict=db_dict,
                           general_services=gs_list, version=APP_VERSION)


@app.route('/api/get_data')
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


# ─── Brands / Models ───────────────────────────────────────────────────────────

@app.route('/api/add_car', methods=['POST'])
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
def delete_brand():
    brand = Brand.query.filter_by(name=(request.get_json() or {}).get('name')).first()
    if not brand:
        return _err('Марку не знайдено')
    db.session.delete(brand)
    db.session.commit()
    return _ok()


@app.route('/api/delete_model', methods=['POST'])
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


# ─── Services ──────────────────────────────────────────────────────────────────

@app.route('/api/add_service', methods=['POST'])
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
def delete_service():
    s = _get(Service, (request.get_json() or {}).get('id'))
    if not s:
        return _err('Послугу не знайдено')
    db.session.delete(s)
    db.session.commit()
    return _ok()


@app.route('/api/add_general_service', methods=['POST'])
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
def delete_gen_service():
    s = _get(GeneralService, (request.get_json() or {}).get('id'))
    if not s:
        return _err('Послугу не знайдено')
    db.session.delete(s)
    db.session.commit()
    return _ok()


# ─── Orders ────────────────────────────────────────────────────────────────────

@app.route('/api/orders')
def get_orders():
    return jsonify([_order_dict(o)
                    for o in Order.query.order_by(Order.created_at.desc()).limit(200)])


@app.route('/api/save_order', methods=['POST'])
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

    o = Order(
        client_id=client_id,
        client_name=client_name,
        car_info=car_info,
        total=int(data.get('total') or 0),
        items=data.get('items') or '[]',
        notes=(data.get('notes') or '').strip() or None,
    )
    db.session.add(o)
    db.session.commit()
    return _ok(id=o.id)


@app.route('/api/edit_order', methods=['POST'])
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
def delete_order():
    o = _get(Order, (request.get_json() or {}).get('id'))
    if not o:
        return _err('Замовлення не знайдено')
    db.session.delete(o)
    db.session.commit()
    return _ok()


# ─── Clients ───────────────────────────────────────────────────────────────────

@app.route('/api/clients')
def get_clients():
    return jsonify([_client_dict(c) for c in Client.query.order_by(Client.name)])


@app.route('/api/client/<int:cid>')
def get_client(cid):
    c = _get(Client, cid)
    if not c:
        return _err('Клієнта не знайдено'), 404
    data = _client_dict(c)
    data['orders'] = [_order_dict(o) for o in
                      Order.query.filter(Order.client_id == cid)
                      .order_by(Order.created_at.desc())]
    return jsonify(data)


@app.route('/api/add_client', methods=['POST'])
def add_client():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return _err("Введіть ім'я клієнта")
    cl = Client(
        name=name,
        phone=(data.get('phone') or '').strip() or None,
        car_info=(data.get('car_info') or '').strip() or None,
        notes=(data.get('notes') or '').strip() or None,
    )
    db.session.add(cl)
    db.session.commit()
    return _ok(id=cl.id)


@app.route('/api/edit_client', methods=['POST'])
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
def delete_client():
    cl = _get(Client, (request.get_json() or {}).get('id'))
    if not cl:
        return _err('Клієнта не знайдено')
    db.session.delete(cl)
    db.session.commit()
    return _ok()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _order_dict(o):
    return {
        'id': o.id,
        'client_id': o.client_id,
        'client_name': o.client_name or '',
        'car_info': o.car_info or '',
        'total': o.total or 0,
        'items': o.items or '[]',
        'notes': o.notes or '',
        'created_at': o.created_at.strftime('%d.%m.%Y %H:%M'),
    }


def _client_dict(c):
    order_count = Order.query.filter(Order.client_id == c.id).count()
    total_spent = db.session.query(db.func.sum(Order.total)).filter(
        Order.client_id == c.id).scalar() or 0
    return {
        'id': c.id,
        'name': c.name,
        'phone': c.phone or '',
        'car_info': c.car_info or '',
        'notes': c.notes or '',
        'created_at': c.created_at.strftime('%d.%m.%Y'),
        'order_count': order_count,
        'total_spent': int(total_spent),
    }


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
