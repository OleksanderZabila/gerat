from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    services = db.relationship('Service', backref='car', lazy=True, cascade="all, delete-orphan")

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'), nullable=False)

class GeneralService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    all_cars = Car.query.all()
    gen_services = GeneralService.query.all()
    cars_db_dict = {car.name: [{"id": s.id, "posluga": s.name, "cina": s.price} for s in car.services] for car in all_cars}
    general_services_list = [{"id": gs.id, "posluga": gs.name, "cina": gs.price} for gs in gen_services]
    return render_template('index.html', cars_db=cars_db_dict, general_services=general_services_list)

@app.route('/api/add_car', methods=['POST'])
def add_car():
    data = request.get_json()
    if Car.query.filter_by(name=data.get('name')).first():
        return jsonify({"success": False, "error": "Авто вже є в базі!"})
    new_car = Car(name=data.get('name'))
    db.session.add(new_car)
    db.session.commit()
    return jsonify({"success": True})

@app.route('/api/delete_car', methods=['POST'])
def delete_car():
    car = Car.query.filter_by(name=request.get_json().get('name')).first()
    if car:
        db.session.delete(car)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/edit_car', methods=['POST'])
def edit_car():
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    car = Car.query.filter_by(name=old_name).first()
    if car:
        if Car.query.filter_by(name=new_name).first() and old_name != new_name:
            return jsonify({"success": False, "error": "Авто з такою назвою вже існує!"})
        car.name = new_name
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Авто не знайдено"})

@app.route('/api/add_service', methods=['POST'])
def add_service():
    data = request.get_json()
    car = Car.query.filter_by(name=data.get('car_name')).first()
    if car:
        new_service = Service(name=data['service_name'], price=data['price'], car_id=car.id)
        db.session.add(new_service)
        db.session.commit()
        # Повертаємо ID нової послуги, щоб JS міг її одразу редагувати/видаляти
        return jsonify({"success": True, "id": new_service.id})
    return jsonify({"success": False})

# НОВИЙ МІСТ: РЕДАГУВАННЯ КОНКРЕТНОЇ ПОСЛУГИ
@app.route('/api/edit_service', methods=['POST'])
def edit_service():
    data = request.get_json()
    service = Service.query.get(data.get('id'))
    if service:
        service.name = data.get('name')
        service.price = data.get('price')
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

# НОВИЙ МІСТ: ВИДАЛЕННЯ КОНКРЕТНОЇ ПОСЛУГИ
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