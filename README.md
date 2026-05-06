# 🔧 Gerat Auto Service — Management System

> Web-based management system for auto repair shops: CRM + Parts Store in one place.  
> Dark UI, role-based access, live dashboard stats, fully offline-capable.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-black?style=flat&logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-3-003b57?style=flat&logo=sqlite&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952b3?style=flat&logo=bootstrap&logoColor=white)
![Version](https://img.shields.io/badge/version-2.4.1-f97316?style=flat)

---

## 📸 Screenshots

| Login | CRM — Vehicle Database |
|-------|------------------------|
| ![Login](docs/screenshots/login.png) | ![CRM](docs/screenshots/crm.png) |

| Orders | Clients | Shop |
|--------|---------|------|
| ![Orders](docs/screenshots/orders.png) | ![Clients](docs/screenshots/clients.png) | ![Shop](docs/screenshots/shop.png) |

---

## ✨ Features

### 🔐 Auth & Roles
| Role | Access |
|------|--------|
| **Admin** | Full access: CRM + Shop + User management |
| **Mechanic** | CRM only — vehicles, services, clients, orders |
| **Cashier** | Shop only — sales, inventory, catalog |

### 🚗 CRM — Auto Repair
- Vehicle database: Brand → Model → Services, real-time search, bulk import
- Services attached to specific models or as general services, one click adds to invoice
- Clients: profile card, full order history, total spending
- Orders: list, search, details, edit, delete, print invoice

### 🏪 Parts Shop
- Catalog with categories, barcodes, purchase and sale prices
- Cart with inline quantity editing — click the number to edit it directly
- Stock is automatically reduced after each sale
- Inventory: sorted out-of-stock 🔴 / low 🟡 / ok 🟢, manual stock adjustments

### 📊 Live Stats in Topbar
Updates every minute: today's orders / CRM revenue / total clients · sales / shop revenue / low-stock count

### 🔫 Barcode Scanner
Infrastructure is ready and commented out. To activate — uncomment 3 lines in `shop.html`. Supports USB HID scanners (detected by keystroke speed < 80ms between characters).

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.0 |
| Database | SQLite |
| Frontend | Bootstrap 5.3 + Bootstrap Icons |
| Security | Werkzeug `pbkdf2:sha256` |

---

## 🚀 Getting Started

```bash
git clone https://github.com/OleksanderZabila/gerat.git
cd gerat
python -m venv venv && venv\Scripts\activate   # Windows
pip install flask flask-sqlalchemy werkzeug
python app.py
```

Open in browser: **http://127.0.0.1:5000** · login `admin` / password `admin`

> ⚠️ Change the default password after first login — click the 🔑 icon in the top-right corner

---

## 📁 Project Structure

```
gerat/
├── app.py                  # Flask app, DB models, all API routes
├── templates/
│   ├── login.html          # Login page with decorative car SVG
│   ├── index.html          # CRM — vehicles, services, clients, orders
│   └── shop.html           # Shop — catalog, cart, sales, inventory
├── static/
│   └── img/
│       ├── car-hero.svg    # Decorative muscle car (login background)
│       ├── car-side.svg    # Car silhouette (CRM empty state)
│       └── engine.svg      # Check-engine icon (error toasts)
└── instance/
    └── gerat.db            # SQLite database (auto-created on first run)
```

---

## 📋 Changelog

| Version | Changes |
|---------|---------|
| **v2.4.1** | Redrawn car-hero SVG (was invisible on dark bg), check-engine icon for error toasts, edit button for general services, missing `/api/edit_general_service` route added |
| **v2.4.0** | Deep navy redesign (`#070d16`), SVG decorations, live stats in topbar, inline qty editing in cart, barcode scanner infrastructure |
| **v2.3.0** | Role-based auth (admin / mechanic / cashier), full shop module, CRM ↔ Shop mode switcher |
| **v2.2.0** | Fixed post-DB-deletion errors, client-to-order linking, hardened JS error handling |
| **v2.1.0** | Clients tab, orders CRUD, invoice print |
| **v2.0.0** | Version statusbar, order editing, client profile with order history |

---

## 📄 License

Private project. All rights reserved © Gerat Auto Service
