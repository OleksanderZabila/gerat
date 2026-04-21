# 🔧 Gerat Auto Service CRM

A full-stack web application designed for auto service stations to manage vehicle databases, track repair services, and dynamically generate customer invoices (repair orders).

## 🚀 Key Features
* **Live Search:** Instant, real-time filtering of vehicles and services.
* **Cascade Data Management:** Full CRUD operations for vehicles with automatic cascading updates/deletions for related services.
* **Dynamic Invoice Calculator:** An interactive cart system that calculates total costs on the fly without page reloads.
* **Responsive UI:** Fully adaptable interface optimized for both desktop and mobile devices.
* **Asynchronous API (AJAX):** Seamless frontend-to-database communication using the JavaScript Fetch API.

## 🛠 Tech Stack
* **Backend:** Python 3, Flask, SQLAlchemy (ORM)
* **Database:** SQLite
* **Frontend:** HTML5, CSS3, Vanilla JavaScript, Bootstrap 5
* **Architecture:** MVC Pattern, RESTful API design

## ⚙️ How to run locally
1. Clone the repository:
   `git clone https://github.com/YOUR_USERNAME/gerat.git`
2. Create and activate a virtual environment:
   `python -m venv venv`
   `venv\Scripts\activate` (for Windows)
3. Install dependencies:
   `pip install -r requirements.txt`
4. Run the application:
   `python app.py`
5. Open your browser and navigate to `http://127.0.0.1:5000`