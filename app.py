"""Local Flask backend for WasteDeal. SQLite is created on first launch."""

from __future__ import annotations

import math
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("WASTEDEAL_DB", str(ROOT / "instance" / "wastedeal.sqlite3"))).expanduser()
if not DATABASE.is_absolute():
    DATABASE = ROOT / DATABASE
DATABASE = DATABASE.resolve()

app = Flask(__name__, static_folder=None, template_folder="templates")
app.secret_key = os.environ.get("WASTEDEAL_SECRET_KEY", "local-development-key-change-before-deployment")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

CARBON_FACTORS = {
    "dry": 0.1,
    "plastic": 2.5,
    "chemical": 5.0,
    "paper": 0.8,
    "organic": 0.5,
    "metal": 0.2,
    "glass": 0.3,
}
STATIC_SUFFIXES = {
    ".html", ".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
    ".webp", ".woff", ".woff2", ".ttf",
}


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DATABASE.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DATABASE, timeout=10.0)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def sample_timestamp(months_ago: int) -> str:
    now = datetime.now()
    month_index = now.year * 12 + now.month - 1 - months_ago
    year, zero_based_month = divmod(month_index, 12)
    return datetime(year, zero_based_month + 1, 10, 12, 0, 0).strftime("%Y-%m-%d %H:%M:%S")


def seed_sample_data() -> None:
    db = get_db()
    if db.execute("SELECT 1 FROM sample_data_state WHERE seed_key = 'starter-v1'").fetchone():
        return

    listings = [
        ("Sample · Riverbend Paper Works", "Cardboard offcuts", "seller1@example.invalid", "Jaipur", "Rajasthan", "302001", 1800, 3.5, 5),
        ("Sample · BrightCycle Polymers", "PET plastic flakes", "seller2@example.invalid", "Ahmedabad", "Gujarat", "380001", 640, 42, 4),
        ("Sample · Northstar Metals", "Aluminum scrap", "seller3@example.invalid", "Faridabad", "Haryana", "121001", 420, 115, 3),
        ("Sample · Mellow Farms Co-op", "Organic fiber waste", "seller4@example.invalid", "Pune", "Maharashtra", "411001", 950, 5.75, 3),
        ("Sample · ClearStream Glass", "Glass cullet", "seller5@example.invalid", "Kolkata", "West Bengal", "700001", 1250, 1.8, 2),
        ("Sample · LoomCycle Textiles", "Cotton textile offcuts", "seller6@example.invalid", "Coimbatore", "Tamil Nadu", "641001", 310, 24, 2),
        ("Sample · ReRubber Industries", "Reclaimed rubber granules", "seller7@example.invalid", "Surat", "Gujarat", "395003", 520, 18, 1),
        ("Sample · CedarBox Packaging", "Mixed paper rolls", "seller8@example.invalid", "Panipat", "Haryana", "132103", 850, 12.5, 0),
        ("Sample · Sampurna Recovery", "Electronic components", "seller9@example.invalid", "Bengaluru", "Karnataka", "560001", 95, 76, 0),
    ]
    db.executemany(
        """INSERT INTO waste_listings
           (industry_name, type_of_waste, email, city, state, pincode, quantity, price, created_at, is_sample)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        [(*row[:8], sample_timestamp(row[8])) for row in listings],
    )

    disposal_requests = [
        ("Laboratory chemical containers", "demo1@example.invalid", "Panipat", "Haryana", "9000000001", 4),
        ("Used industrial batteries", "demo2@example.invalid", "Pune", "Maharashtra", "9000000002", 3),
        ("Paint and solvent residue", "demo3@example.invalid", "Jaipur", "Rajasthan", "9000000003", 1),
        ("Contaminated packaging", "demo4@example.invalid", "Surat", "Gujarat", "9000000004", 0),
    ]
    db.executemany(
        """INSERT INTO disposal_requests
           (waste_type, email, city, state, mobile_no, created_at, is_sample)
           VALUES (?, ?, ?, ?, ?, ?, 1)""",
        [(*row[:5], sample_timestamp(row[5])) for row in disposal_requests],
    )

    contact_messages = [
        ("Demo Buyer", "buyer1@example.invalid", "Finding recycled packaging", "Sample contact message for the analytics dashboard.", 3),
        ("Demo Supplier", "supplier1@example.invalid", "Listing accepted materials", "Sample contact message for the analytics dashboard.", 1),
        ("Demo Buyer", "buyer2@example.invalid", "Bulk material availability", "Sample contact message for the analytics dashboard.", 0),
    ]
    db.executemany(
        """INSERT INTO contact_messages (name, email, subject, message, created_at, is_sample)
           VALUES (?, ?, ?, ?, ?, 1)""",
        [(*row[:4], sample_timestamp(row[4])) for row in contact_messages],
    )

    quote_requests = [
        ("Panipat", "Delhi", "850 kg", "2 pallets", "Demo Buyer", "quote1@example.invalid", "9000000011", "Sample quote request.", 4),
        ("Ahmedabad", "Mumbai", "640 kg", "1 pallet", "Demo Buyer", "quote2@example.invalid", "9000000012", "Sample quote request.", 2),
        ("Jaipur", "Gurugram", "1.8 tonnes", "3 pallets", "Demo Buyer", "quote3@example.invalid", "9000000013", "Sample quote request.", 0),
    ]
    db.executemany(
        """INSERT INTO quote_requests
           (departure, delivery, weight, dimensions, name, email, phone, message, created_at, is_sample)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        [(*row[:8], sample_timestamp(row[8])) for row in quote_requests],
    )
    db.execute("INSERT INTO sample_data_state (seed_key) VALUES ('starter-v1')")
    db.commit()


def init_db() -> None:
    with app.app_context():
        get_db().executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS waste_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                industry_name TEXT NOT NULL,
                type_of_waste TEXT NOT NULL,
                email TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                pincode TEXT NOT NULL,
                quantity REAL NOT NULL CHECK (quantity > 0),
                price REAL NOT NULL CHECK (price >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_sample INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS disposal_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waste_type TEXT NOT NULL,
                email TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                mobile_no TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_sample INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_sample INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS quote_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                departure TEXT NOT NULL,
                delivery TEXT NOT NULL,
                weight TEXT NOT NULL,
                dimensions TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_sample INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS carbon_factors (
                waste_type TEXT PRIMARY KEY COLLATE NOCASE,
                carbon_factor REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sample_data_state (
                seed_key TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_waste_listings_created_at_id
                ON waste_listings (created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_waste_listings_material
                ON waste_listings (type_of_waste);
            CREATE INDEX IF NOT EXISTS idx_waste_listings_location
                ON waste_listings (city, state);
            """
        )
        for table_name in ("waste_listings", "disposal_requests", "contact_messages", "quote_requests"):
            columns = {row["name"] for row in get_db().execute(f"PRAGMA table_info({table_name})")}
            if "is_sample" not in columns:
                get_db().execute(f"ALTER TABLE {table_name} ADD COLUMN is_sample INTEGER NOT NULL DEFAULT 0")
        get_db().executemany(
            "INSERT OR IGNORE INTO carbon_factors (waste_type, carbon_factor) VALUES (?, ?)",
            CARBON_FACTORS.items(),
        )
        get_db().commit()
        seed_sample_data()


def page_message(title: str, message: str, *, success: bool = True, status: int = 200):
    return render_template("message.html", title=title, message=message, success=success), status


def valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()))


@app.get("/")
@app.get("/index.php")
def home():
    user = None
    if session.get("user_id"):
        user = get_db().execute("SELECT id, name FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return render_template("home.html", user=user)


@app.get("/analytics")
def analytics():
    db = get_db()
    listing_count = db.execute("SELECT COUNT(*) AS total FROM waste_listings").fetchone()["total"]
    listing_totals = db.execute(
        "SELECT COALESCE(SUM(quantity), 0) AS quantity, COALESCE(AVG(price), 0) AS avg_price FROM waste_listings"
    ).fetchone()
    disposal_count = db.execute("SELECT COUNT(*) FROM disposal_requests").fetchone()[0]
    contact_count = db.execute("SELECT COUNT(*) FROM contact_messages").fetchone()[0]
    quote_count = db.execute("SELECT COUNT(*) FROM quote_requests").fetchone()[0]
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    sample_count = sum(
        db.execute(f"SELECT COUNT(*) FROM {table_name} WHERE is_sample = 1").fetchone()[0]
        for table_name in ("waste_listings", "disposal_requests", "contact_messages", "quote_requests")
    )

    now = datetime.now()
    first_visible_month = now.year * 12 + now.month - 1 - 5
    first_year, first_zero_based_month = divmod(first_visible_month, 12)
    first_visible_date = datetime(first_year, first_zero_based_month + 1, 1)
    monthly_rows = db.execute(
        """SELECT substr(created_at, 1, 7) AS month_key, COUNT(*) AS total
           FROM waste_listings WHERE created_at >= ? GROUP BY month_key""",
        (first_visible_date.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchall()
    month_counts = {row["month_key"]: row["total"] for row in monthly_rows}
    months = []
    for months_ago in range(5, -1, -1):
        month_index = now.year * 12 + now.month - 1 - months_ago
        year, zero_based_month = divmod(month_index, 12)
        month_date = datetime(year, zero_based_month + 1, 1)
        key = month_date.strftime("%Y-%m")
        months.append({"label": month_date.strftime("%b"), "total": month_counts.get(key, 0)})
    max_monthly = max((item["total"] for item in months), default=0) or 1
    for item in months:
        item["height"] = round(item["total"] / max_monthly * 100) if item["total"] else 0

    materials = db.execute(
        """SELECT type_of_waste, SUM(quantity) AS quantity, COUNT(*) AS listings
           FROM waste_listings GROUP BY type_of_waste ORDER BY quantity DESC LIMIT 6"""
    ).fetchall()
    max_material_quantity = max((row["quantity"] for row in materials), default=0) or 1
    material_mix = [
        {"name": row["type_of_waste"], "quantity": round(row["quantity"], 1), "listings": row["listings"],
         "width": round(row["quantity"] / max_material_quantity * 100)}
        for row in materials
    ]
    request_mix = [
        {"name": "Disposal requests", "count": disposal_count},
        {"name": "Quote requests", "count": quote_count},
        {"name": "Contact messages", "count": contact_count},
    ]
    max_requests = max((row["count"] for row in request_mix), default=0) or 1
    for row in request_mix:
        row["width"] = round(row["count"] / max_requests * 100)
    locations = db.execute(
        """SELECT city, state, COUNT(*) AS listings, SUM(quantity) AS quantity
           FROM waste_listings GROUP BY city, state ORDER BY listings DESC, quantity DESC LIMIT 5"""
    ).fetchall()

    return render_template(
        "analytics.html",
        listing_count=listing_count,
        quantity_total=round(listing_totals["quantity"], 1),
        average_price=round(listing_totals["avg_price"], 2),
        total_requests=disposal_count + contact_count + quote_count,
        user_count=user_count,
        sample_count=sample_count,
        months=months,
        material_mix=material_mix,
        request_mix=request_mix,
        locations=locations,
    )


@app.route("/login", methods=["GET", "POST"])
@app.route("/login.php", methods=["GET", "POST"])
def login():
    error = None
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("register_waste_page"))
        error = "The email or password is incorrect. Please try again."
    return render_template("login.html", error=error, email=email)


@app.route("/signup", methods=["GET", "POST"])
@app.route("/process-signup.php", methods=["POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", error=None, values={})

    values = {key: request.form.get(key, "").strip() for key in ("name", "email")}
    password = request.form.get("password", "")
    confirmation = request.form.get("password_confirmation", "")
    error = None
    if len(values["name"]) < 2:
        error = "Please enter your name (at least 2 characters)."
    elif not valid_email(values["email"]):
        error = "Please enter a valid email address."
    elif len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        error = "Use at least 8 characters, including a letter and a number."
    elif password != confirmation:
        error = "The passwords do not match."
    elif get_db().execute("SELECT 1 FROM users WHERE email = ?", (values["email"],)).fetchone():
        error = "An account with this email already exists."

    if error:
        return render_template("signup.html", error=error, values=values), 400

    get_db().execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (values["name"], values["email"], generate_password_hash(password)),
    )
    get_db().commit()
    return page_message("Account created", "Your account is ready. You can now sign in.")


@app.get("/logout")
@app.get("/logout.php")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/email-available")
@app.get("/validate-email.php")
def email_available():
    email = request.args.get("email", "").strip()
    exists = bool(email) and get_db().execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone() is not None
    return jsonify(available=not exists)


@app.get("/registerwaste.html")
def register_waste_page():
    return render_template("register_waste.html")


@app.get("/search.html")
def search_page():
    return render_template("search.html")


@app.get("/wastedisposal.html")
def disposal_page():
    return render_template("disposal.html")


@app.get("/contact.html")
def contact_page():
    return render_template("contact.html")


@app.get("/get-a-quote.html")
def quote_page():
    return render_template("quote.html")


@app.post("/register-waste")
@app.post("/RegisterWasteProcess.php")
def register_waste():
    fields = ("industry_name", "type_of_waste", "email", "city", "state", "pincode")
    values = {key: request.form.get(key, "").strip() for key in fields}
    try:
        quantity = float(request.form.get("quantity", ""))
        price = float(request.form.get("price", ""))
    except ValueError:
        return page_message("Listing not saved", "Enter a valid quantity and price.", success=False, status=400)
    if any(not value for value in values.values()) or not valid_email(values["email"]):
        return page_message("Listing not saved", "Complete every field and enter a valid email address.", success=False, status=400)
    if not math.isfinite(quantity) or not math.isfinite(price) or quantity <= 0 or price < 0:
        return page_message("Listing not saved", "Quantity must be greater than zero and price cannot be negative.", success=False, status=400)

    get_db().execute(
        """INSERT INTO waste_listings
           (user_id, industry_name, type_of_waste, email, city, state, pincode, quantity, price)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session.get("user_id"), *(values[field] for field in fields), quantity, price),
    )
    get_db().commit()
    return page_message("Waste listing saved", "Your listing is now available in WasteDeal search results.")


@app.route("/search", methods=["GET", "POST"])
@app.route("/search-results.php", methods=["POST"])
def search():
    if request.method == "GET":
        return redirect("/search.html")
    term = request.form.get("waste_type", "").strip()
    if not term:
        return page_message("Search waste", "Enter a waste type to search for.", success=False, status=400)
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    listings = get_db().execute(
        """SELECT id, industry_name, type_of_waste, email, city, state, pincode, quantity, price, is_sample
           FROM waste_listings WHERE type_of_waste LIKE ? ESCAPE '\\' ORDER BY created_at DESC, id DESC""",
        (f"%{escaped}%",),
    ).fetchall()
    return render_template("search_results.html", term=term, listings=listings)


@app.post("/disposal")
@app.post("/process-disposal.php")
def disposal():
    fields = {
        "waste_type": request.form.get("wasteType", "").strip(),
        "email": request.form.get("email", "").strip(),
        "city": request.form.get("city", "").strip(),
        "state": request.form.get("state", "").strip(),
        "mobile_no": request.form.get("mobileNo", "").strip(),
    }
    if (
        any(not value for value in fields.values())
        or not valid_email(fields["email"])
        or len(fields["mobile_no"]) != 10
        or not fields["mobile_no"].isdigit()
    ):
        return page_message("Request not saved", "Complete every field, enter a valid email, and provide a 10-digit mobile number.", success=False, status=400)
    get_db().execute(
        "INSERT INTO disposal_requests (waste_type, email, city, state, mobile_no) VALUES (?, ?, ?, ?, ?)",
        tuple(fields.values()),
    )
    get_db().commit()
    return page_message("Disposal request received", "Your disposal request has been saved. The WasteDeal team can follow up using the contact details you provided.")


@app.post("/contact")
@app.post("/forms/contact.php")
def contact():
    fields = tuple(request.form.get(key, "").strip() for key in ("name", "email", "subject", "message"))
    if any(not value for value in fields) or not valid_email(fields[1]):
        return page_message("Message not saved", "Complete every field and enter a valid email address.", success=False, status=400)
    get_db().execute("INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)", fields)
    get_db().commit()
    return page_message("Message received", "Your message has been saved. Thank you for contacting WasteDeal.")


@app.post("/quote")
@app.post("/forms/quote.php")
def quote():
    keys = ("departure", "delivery", "weight", "dimensions", "name", "email", "phone", "message")
    fields = tuple(request.form.get(key, "").strip() for key in keys)
    if any(not value for value in fields) or not valid_email(fields[5]):
        return page_message("Quote request not saved", "Complete every field and enter a valid email address.", success=False, status=400)
    get_db().execute(
        """INSERT INTO quote_requests
           (departure, delivery, weight, dimensions, name, email, phone, message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        fields,
    )
    get_db().commit()
    return page_message("Quote request received", "Your quote request has been saved. Thank you.")


@app.get("/carbon-factors")
@app.get("/get_carbon_factors.php")
def carbon_factors():
    waste_type = request.args.get("wasteType", "").strip()
    factor = get_db().execute(
        "SELECT carbon_factor FROM carbon_factors WHERE waste_type = ?", (waste_type,)
    ).fetchone()
    return jsonify(carbon_factor=factor["carbon_factor"] if factor else None)


@app.get("/payment_success.php")
def payment_not_configured():
    return page_message(
        "Online payment unavailable",
        "This local project has no payment gateway configured. Contact the listing owner directly to discuss a purchase.",
        success=False,
        status=501,
    )


@app.get("/<path:filename>")
def project_file(filename: str):
    target = (ROOT / filename).resolve()
    hidden_path = any(part.startswith(".") for part in Path(filename).parts)
    if not target.is_relative_to(ROOT) or hidden_path or target.suffix.lower() not in STATIC_SUFFIXES:
        abort(404)
    if not target.is_file():
        abort(404)
    return send_from_directory(ROOT, filename)


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("WASTEDEAL_DEBUG") == "1")
