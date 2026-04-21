import re  # ДОДАНО: Бібліотека для сканування тексту за шаблонами
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


with app.app_context():
    db.create_all()


@app.route('/')
def home():
    all_brands = Brand.query.all()
    gen_services = GeneralService.query.all()

    db_dict = {}
    for b in all_brands:
        db_dict[b.name] = {}
        for m in b.models:
            db_dict[b.name][m.name] = [{"id": s.id, "posluga": s.name, "cina": s.price} for s in m.services]

    general_services_list = [{"id": gs.id, "posluga": gs.name, "cina": gs.price} for gs in gen_services]
    return render_template('index.html', db_dict=db_dict, general_services=general_services_list)


# ==========================================
# НОВИЙ МІСТ: МАСОВИЙ ІМПОРТ З ШІ
# ==========================================
@app.route('/api/bulk_import', methods=['POST'])
def bulk_import():
    data = request.get_json()
    text = data.get('text', '')

    # МАГІЯ ТУТ: Шукаємо шаблон "Марка" {Модель} [Послуга] |Ціна|
    pattern = r'"([^"]+)"\s*\{([^}]+)\}\s*\[([^\]]+)\]\s*\|\s*(\d+)\s*\|'
    matches = re.findall(pattern, text)

    if not matches:
        return jsonify({"success": False, "error": "Не знайдено жодного запису у правильному форматі."})

    added_count = 0
    for b_name, m_name, s_name, price_str in matches:
        b_name = b_name.strip()
        m_name = m_name.strip()
        s_name = s_name.strip()
        price = int(price_str.strip())

        # 1. Перевіряємо, чи є вже така марка, якщо ні - створюємо
        brand = Brand.query.filter_by(name=b_name).first()
        if not brand:
            brand = Brand(name=b_name)
            db.session.add(brand)
            db.session.flush()  # Зберігаємо тимчасово, щоб отримати ID

        # 2. Перевіряємо модель
        model = CarModel.query.filter_by(name=m_name, brand_id=brand.id).first()
        if not model:
            model = CarModel(name=m_name, brand_id=brand.id)
            db.session.add(model)
            db.session.flush()

        # 3. Перевіряємо, чи немає вже точно такої ж послуги (Захист від дублів!)
        service = Service.query.filter_by(name=s_name, model_id=model.id).first()
        if not service:
            new_srv = Service(name=s_name, price=price, model_id=model.id)
            db.session.add(new_srv)
            added_count += 1  # Рахуємо тільки успішно додані НОВІ послуги

    db.session.commit()  # Фіксуємо всі зміни в базу даних
    return jsonify({"success": True, "added": added_count})


@app.route('/api/add_service', methods=['POST'])
def add_service():
    data = request.get_json()
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if brand:
        model = CarModel.query.filter_by(name=data.get('model'), brand_id=brand.id).first()
        if model:
            new_service = Service(name=data['service_name'], price=data['price'], model_id=model.id)
            db.session.add(new_service)
            db.session.commit()
            return jsonify({"success": True, "id": new_service.id})
    return jsonify({"success": False})


@app.route('/api/delete_service', methods=['POST'])
def delete_service():
    service = Service.query.get(request.get_json().get('id'))
    if service:
        db.session.delete(service)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})


@app.route('/api/add_general_service', methods=['POST'])
def add_gen_service():
    data = request.get_json()
    new_gs = GeneralService(name=data['name'], price=data['price'])
    db.session.add(new_gs)
    db.session.commit()
    return jsonify({"success": True, "id": new_gs.id})


@app.route('/api/delete_general_service', methods=['POST'])
def delete_gen_service():
    gs = GeneralService.query.get(request.get_json().get('id'))
    if gs:
        db.session.delete(gs)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)