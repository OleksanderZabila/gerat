import re
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- МОДЕЛІ ---
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

# --- МАРШРУТИ ---
@app.route('/')
def index():
    brands = Brand.query.all()
    db_dict = {}
    for b in brands:
        db_dict[b.name] = {}
        for m in b.models:
            db_dict[b.name][m.name] = [{"id": s.id, "posluga": s.name, "cina": s.price} for s in m.services]
    gs = GeneralService.query.all()
    gs_list = [{"id": s.id, "posluga": s.name, "cina": s.price} for s in gs]
    return render_template('index.html', db_dict=db_dict, general_services=gs_list)

@app.route('/api/add_car', methods=['POST'])
def add_car():
    data = request.get_json()
    b_name = data.get('brand').strip()
    m_name = data.get('model').strip()
    if not b_name: return jsonify({"success": False})
    brand = Brand.query.filter_by(name=b_name).first()
    if not brand:
        brand = Brand(name=b_name); db.session.add(brand); db.session.commit()
    if m_name:
        model = CarModel.query.filter_by(name=m_name, brand_id=brand.id).first()
        if not model:
            model = CarModel(name=m_name, brand_id=brand.id); db.session.add(model); db.session.commit()
    return jsonify({"success": True})

@app.route('/api/rename_brand', methods=['POST'])
def rename_brand():
    data = request.get_json()
    brand = Brand.query.filter_by(name=data.get('old_name')).first()
    if brand:
        brand.name = data.get('new_name').strip(); db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/rename_model', methods=['POST'])
def rename_model():
    data = request.get_json()
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if brand:
        model = CarModel.query.filter_by(name=data.get('old_name'), brand_id=brand.id).first()
        if model:
            model.name = data.get('new_name').strip(); db.session.commit()
            return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/bulk_import', methods=['POST'])
def bulk_import():
    data = request.get_json()
    matches = re.findall(r'"([^"]+)"\s*\{([^}]+)\}\s*\[([^\]]+)\]\s*\|\s*(\d+)\s*\|', data.get('text', ''))
    added = 0
    for b_name, m_name, s_name, price in matches:
        brand = Brand.query.filter_by(name=b_name.strip()).first()
        if not brand: brand = Brand(name=b_name.strip()); db.session.add(brand); db.session.commit()
        model = CarModel.query.filter_by(name=m_name.strip(), brand_id=brand.id).first()
        if not model: model = CarModel(name=m_name.strip(), brand_id=brand.id); db.session.add(model); db.session.commit()
        if not Service.query.filter_by(name=s_name.strip(), model_id=model.id).first():
            db.session.add(Service(name=s_name.strip(), price=int(price), model_id=model.id)); added += 1
    db.session.commit()
    return jsonify({"success": True, "added": added})

@app.route('/api/add_service', methods=['POST'])
def add_service():
    data = request.get_json()
    brand = Brand.query.filter_by(name=data.get('brand')).first()
    if brand:
        model = CarModel.query.filter_by(name=data.get('model'), brand_id=brand.id).first()
        if model:
            new = Service(name=data['service_name'], price=data['price'], model_id=model.id)
            db.session.add(new); db.session.commit(); return jsonify({"success": True, "id": new.id})
    return jsonify({"success": False})

@app.route('/api/edit_service', methods=['POST'])
def edit_service():
    data = request.get_json(); s = Service.query.get(data.get('id'))
    if s: s.price = int(data.get('price')); db.session.commit(); return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/delete_service', methods=['POST'])
def delete_service():
    s = Service.query.get(request.get_json().get('id'))
    if s: db.session.delete(s); db.session.commit(); return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/delete_brand', methods=['POST'])
def delete_brand():
    b = Brand.query.filter_by(name=request.get_json().get('name')).first()
    if b: db.session.delete(b); db.session.commit(); return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/delete_model', methods=['POST'])
def delete_model():
    data = request.get_json(); b = Brand.query.filter_by(name=data.get('brand')).first()
    if b:
        m = CarModel.query.filter_by(name=data.get('model'), brand_id=b.id).first()
        if m: db.session.delete(m); db.session.commit(); return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/add_general_service', methods=['POST'])
def add_gen_service():
    data = request.get_json()
    new = GeneralService(name=data['name'], price=data['price']); db.session.add(new); db.session.commit()
    return jsonify({"success": True, "id": new.id})

@app.route('/api/delete_general_service', methods=['POST'])
def delete_gen_service():
    s = GeneralService.query.get(request.get_json().get('id'))
    if s: db.session.delete(s); db.session.commit(); return jsonify({"success": True})
    return jsonify({"success": False})

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)