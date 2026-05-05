import re
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Brand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    models = db.relationship('CarModel', backref='brand', lazy=True, cascade="all, delete-orphan")


class CarModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'), nullable=False)
    services = db.relationship('Service', backref='model', lazy=True, cascade="all, delete-orphan")


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
    orders = db.relationship('Order', backref='client', lazy=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    client_name = db.Column(db.String(200))
    car_info = db.Column(db.String(200))
    total = db.Column(db.Integer, default=0)
    items = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def _ok(**kwargs):
    return jsonify({"success": True, **kwargs})

def _err(msg="Помилка"):
    return jsonify({"success": False, "error": msg}), 400


# ── Main page ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    brands = Brand.query.all()
    db_dict = {}
    for b in brands:
        db_dict[b.name] = {}
        for m in b.models:
            db_dict[b.name][m.name] = [
                {"id": s.id, "posluga": s.name, "cina": s.price} for s in m.services
            ]
    gs = GeneralService.query.all()
    gs_list = [{"id": s.id, "posluga": s.name, "cina": s.price} for s in gs]
    return render_template('index.html', db_dict=db_dict, general_services=gs_list)


@app.route('/api/get_data')
def get_data():
    brands = Brand.query.all()
    db_dict = {}
    for b in brands:
        db_dict[b.name] = {}
        for m in b.models:
            db_dict[b.name][m.name] = [
                {"id": s.id, "posluga": s.name, "cina": s.price} for s in m.services
            ]
    gs = GeneralService.query.all()
    gs_list = [{"id": s.id, "posluga": s.name, "cina": s.price} for s in gs]
    return jsonify({"db_dict": db_dict, "general_services": gs_list})


# ── Cars / brands / models ─────────────────────────────────────────────────

@app.route('/api/add_car', methods=['POST'])
def add_car():
    data = request.get_json() or {}
    b_name = (data.get('brand') or '').strip()
    m_name = (data.get('model') or '').strip()
    if not b_name:
        return _err("Введіть назву марки")
    brand = Brand.query.filter_by(name=b_name).first()
    if not brand:
        brand = Brand(name=b_name)
        db.session.add(brand)
        db.session.commit()
    if m_name:
        model = CarModel.query.filter_by(name=m_name, brand_id=brand.id).first()
        if not model:
            model = CarModel(name=m_name, brand_id=brand.id)
            db.session.add(model)
            db.session.commit()
    return _ok()


@app.route('/api/rename_brand', methods=['POST'])
def rename_brand():
    data = request.get_json() or {}
    new_name = (data.get('new_name') or '').strip()
    if not new_name:
        return _err("Нова назва не може бути порожньою")
    brand = Brand.query.filter_by(name=data.get('old_name')).first()
    if not brand:
        return _err("Марку не знайдено")
    if Brand.query.filter_by(name=new_name).first():
        return _err("Марка з такою назвою вже існує")
    brand.name = new_name
    db.session.commit()
    return _ok()


@app.route('/api/rename_model', methods=['POST'])
def rename_model():
    data = request.get_json() or {}
    new_name = (data.get('new_name') or '').strip()
    if not new_name:
        return _err("Нова назва не може бути порожньою")
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if not brand:
        return _err("Марку не знайдено")
    model = CarModel.query.filter_by(name=data.get('old_name'), brand_id=brand.id).first()
    if not model:
        return _err("Модель не знайдено")
    model.name = new_name
    db.session.commit()
    return _ok()


@app.route('/api/bulk_import', methods=['POST'])
def bulk_import():
    data = request.get_json() or {}
    text = data.get('text', '')
    matches = re.findall(r'"([^"]+)"\s*\{([^}]+)\}\s*\[([^\]]+)\]\s*\|\s*(\d+)\s*\|', text)
    added = 0
    for b_name, m_name, s_name, price in matches:
        b_name, m_name, s_name = b_name.strip(), m_name.strip(), s_name.strip()
        brand = Brand.query.filter_by(name=b_name).first()
        if not brand:
            brand = Brand(name=b_name)
            db.session.add(brand)
            db.session.commit()
        model = CarModel.query.filter_by(name=m_name, brand_id=brand.id).first()
        if not model:
            model = CarModel(name=m_name, brand_id=brand.id)
            db.session.add(model)
            db.session.commit()
        if not Service.query.filter_by(name=s_name, model_id=model.id).first():
            db.session.add(Service(name=s_name, price=int(price), model_id=model.id))
            added += 1
    db.session.commit()
    return _ok(added=added)


@app.route('/api/delete_brand', methods=['POST'])
def delete_brand():
    brand = Brand.query.filter_by(name=(request.get_json() or {}).get('name')).first()
    if not brand:
        return _err("Марку не знайдено")
    db.session.delete(brand)
    db.session.commit()
    return _ok()


@app.route('/api/delete_model', methods=['POST'])
def delete_model():
    data = request.get_json() or {}
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if not brand:
        return _err("Марку не знайдено")
    model = CarModel.query.filter_by(name=data.get('model'), brand_id=brand.id).first()
    if not model:
        return _err("Модель не знайдено")
    db.session.delete(model)
    db.session.commit()
    return _ok()


# ── Services ───────────────────────────────────────────────────────────────

@app.route('/api/add_service', methods=['POST'])
def add_service():
    data = request.get_json() or {}
    name = (data.get('service_name') or '').strip()
    if not name:
        return _err("Введіть назву послуги")
    try:
        price = int(data.get('price'))
        if price < 0:
            raise ValueError
    except (TypeError, ValueError):
        return _err("Некоректна ціна")
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if not brand:
        return _err("Марку не знайдено")
    model = CarModel.query.filter_by(name=data.get('model'), brand_id=brand.id).first()
    if not model:
        return _err("Модель не знайдено")
    srv = Service(name=name, price=price, model_id=model.id)
    db.session.add(srv)
    db.session.commit()
    return _ok(id=srv.id)


@app.route('/api/edit_service', methods=['POST'])
def edit_service():
    data = request.get_json() or {}
    srv = Service.query.get(data.get('id'))
    if not srv:
        return _err("Послугу не знайдено")
    new_name = (data.get('name') or '').strip()
    if new_name:
        srv.name = new_name
    try:
        price = int(data.get('price'))
        if price < 0:
            raise ValueError
        srv.price = price
    except (TypeError, ValueError):
        return _err("Некоректна ціна")
    db.session.commit()
    return _ok()


@app.route('/api/delete_service', methods=['POST'])
def delete_service():
    srv = Service.query.get((request.get_json() or {}).get('id'))
    if not srv:
        return _err("Послугу не знайдено")
    db.session.delete(srv)
    db.session.commit()
    return _ok()


@app.route('/api/add_general_service', methods=['POST'])
def add_gen_service():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return _err("Введіть назву")
    try:
        price = int(data.get('price'))
        if price < 0:
            raise ValueError
    except (TypeError, ValueError):
        return _err("Некоректна ціна")
    srv = GeneralService(name=name, price=price)
    db.session.add(srv)
    db.session.commit()
    return _ok(id=srv.id)


@app.route('/api/delete_general_service', methods=['POST'])
def delete_gen_service():
    srv = GeneralService.query.get((request.get_json() or {}).get('id'))
    if not srv:
        return _err("Послугу не знайдено")
    db.session.delete(srv)
    db.session.commit()
    return _ok()


# ── Orders ─────────────────────────────────────────────────────────────────

@app.route('/api/orders')
def get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).limit(200).all()
    return jsonify([_order_dict(o) for o in orders])


@app.route('/api/save_order', methods=['POST'])
def save_order():
    data = request.get_json() or {}
    client_name = (data.get('client_name') or '').strip() or None
    car_info = (data.get('car_info') or '').strip() or None
    client_id = data.get('client_id') or None

    # auto-link to existing client by id
    if not client_id and client_name:
        cl = Client.query.filter(
            Client.name.ilike(client_name)
        ).first()
        if cl:
            client_id = cl.id

    order = Order(
        client_id=client_id,
        client_name=client_name,
        car_info=car_info,
        total=int(data.get('total') or 0),
        items=data.get('items') or '[]',
        notes=(data.get('notes') or '').strip() or None,
    )
    db.session.add(order)
    db.session.commit()
    return _ok(id=order.id)


@app.route('/api/edit_order', methods=['POST'])
def edit_order():
    data = request.get_json() or {}
    order = Order.query.get(data.get('id'))
    if not order:
        return _err("Замовлення не знайдено")
    order.client_name = (data.get('client_name') or '').strip() or order.client_name
    order.car_info = (data.get('car_info') or '').strip() or None
    order.notes = (data.get('notes') or '').strip() or None
    db.session.commit()
    return _ok()


@app.route('/api/delete_order', methods=['POST'])
def delete_order():
    order = Order.query.get((request.get_json() or {}).get('id'))
    if not order:
        return _err("Замовлення не знайдено")
    db.session.delete(order)
    db.session.commit()
    return _ok()


# ── Clients ────────────────────────────────────────────────────────────────

@app.route('/api/clients')
def get_clients():
    clients = Client.query.order_by(Client.name).all()
    return jsonify([_client_dict(c) for c in clients])


@app.route('/api/client/<int:cid>')
def get_client(cid):
    c = Client.query.get_or_404(cid)
    data = _client_dict(c)
    data['orders'] = [_order_dict(o) for o in
                      Order.query.filter_by(client_id=cid).order_by(Order.created_at.desc()).all()]
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
    cl = Client.query.get(data.get('id'))
    if not cl:
        return _err("Клієнта не знайдено")
    cl.name = (data.get('name') or cl.name).strip()
    cl.phone = (data.get('phone') or '').strip() or None
    cl.car_info = (data.get('car_info') or '').strip() or None
    cl.notes = (data.get('notes') or '').strip() or None
    db.session.commit()
    return _ok()


@app.route('/api/delete_client', methods=['POST'])
def delete_client():
    cl = Client.query.get((request.get_json() or {}).get('id'))
    if not cl:
        return _err("Клієнта не знайдено")
    db.session.delete(cl)
    db.session.commit()
    return _ok()


# ── Helpers ────────────────────────────────────────────────────────────────

def _order_dict(o):
    return {
        "id": o.id,
        "client_id": o.client_id,
        "client_name": o.client_name or '',
        "car_info": o.car_info or '',
        "total": o.total,
        "items": o.items or '[]',
        "notes": o.notes or '',
        "created_at": o.created_at.strftime('%d.%m.%Y %H:%M'),
    }


def _client_dict(c):
    order_count = Order.query.filter_by(client_id=c.id).count()
    total_spent = db.session.query(
        db.func.sum(Order.total)
    ).filter_by(client_id=c.id).scalar() or 0
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone or '',
        "car_info": c.car_info or '',
        "notes": c.notes or '',
        "created_at": c.created_at.strftime('%d.%m.%Y'),
        "order_count": order_count,
        "total_spent": total_spent,
    }


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
