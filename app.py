import sqlite3
import os
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, g, Response
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "boda-sofia-alejandro-2025-secret")

DB_PATH = os.path.join(os.path.dirname(__file__), "boda.db")

# ──────────────────────────────────────────────────────────
#  DATOS DE LA BODA  (edita aquí)
# ──────────────────────────────────────────────────────────
WEDDING = {
    "groom": "Janine",
    "bride": "Iván",
    "date": "15 de Noviembre, 2026",
    "date_iso": "2026-11-15T17:00:00",
    "ceremony": {
        "name": "Parroquia de la Divina Providencia",
        "address": "C. Roma 1 esquina con Andador 1, Los Sauces, 76114 Santiago de Querétaro, Qro.",
        "time": "12:00 PM",
    },
    "reception": {
        "name": 'Salón de Fiestas "Los Arcos"',
        "address": "Campanitas 3, Rancho San Pedro, 76117 Santiago de Querétaro, Qro.",
        "time": "3:00 PM",
    },
    "rsvp_deadline": "30 Septiembre, 2025",
    "contact_email": "Contacto de la Novia: +52 442 329 6104",
    "story": [
        {"year": "2024", "title": "El primer encuentro",
         "description": "Nos conocimos una noche del ultimo día de Enero, en el negocio de los papás de Janine.",
         "icon": "pi-heart"},
        {"year": "2025", "title": "La primera cita",
         "description": "Un rollo de sushi, un helado y la certeza de querer seguir viéndonos todos los días.",
         "icon": "pi-star"},
        {"year": "2026", "title": "Vivir juntos",
         "description": "Encontramos una pequeña casa en Querétaro, una casa que construimos con mucho amor.",
         "icon": "pi-home"},
        {"year": "2026", "title": "La propuesta",
         "description": "En la última noche del año 2025, Iván  se arrodilló y preguntó lo que ya ambos sabían. La respuesta fue sí.",
         "icon": "pi-gift"},
    ],
    "dress_colors": [
        {"name": "Borgoña",    "hex": "#7B2D42"},
        {"name": "Ciruela",    "hex": "#7B3FA0"},
        {"name": "Lavanda",    "hex": "#6B3A5A"},
        {"name": "Medianoche", "hex": "#2C2C3A"},
    ],
    "dress_avoid": [
        "Vestido blanco o marfil (reservado para la novia)",
        "Colores neón o estampados muy llamativos",
        "Ropa muy casual: jeans, tenis o playeras",
        "Morado intenso (color principal de la boda)",
    ],
    # ── Credenciales del panel ─────────────────────────
    "admin_user": "novios",
    "admin_pass": "boda2025",
}


# ──────────────────────────────────────────────────────────
#  BASE DE DATOS
# ──────────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS rsvp (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                email       TEXT    NOT NULL UNIQUE,
                attending   INTEGER NOT NULL DEFAULT 1,
                guests      INTEGER NOT NULL DEFAULT 1,
                message     TEXT,
                created_at  TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        db.commit()


# ──────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def get_stats(db):
    total       = db.execute("SELECT COUNT(*) FROM rsvp").fetchone()[0]
    row         = db.execute("SELECT COUNT(*), COALESCE(SUM(guests),0) FROM rsvp WHERE attending=1").fetchone()
    attending   = row[0]
    total_pax   = row[1]
    not_att     = db.execute("SELECT COUNT(*) FROM rsvp WHERE attending=0").fetchone()[0]
    return {"total": total, "attending": attending,
            "not_attending": not_att, "total_guests": total_pax}


# ──────────────────────────────────────────────────────────
#  RUTAS PÚBLICAS
# ──────────────────────────────────────────────────────────
@app.route("/")
def index():
    wedding_dt = datetime.fromisoformat(WEDDING["date_iso"])
    days_left  = max((wedding_dt - datetime.now()).days, 0)
    return render_template("index.html", wedding=WEDDING, days_left=days_left)


@app.route("/rsvp", methods=["POST"])
def rsvp():
    data      = request.get_json() or {}
    name      = data.get("name", "").strip()
    email     = data.get("email", "").strip()
    attending = bool(data.get("attending", True))
    guests    = max(1, min(int(data.get("guests", 1)), 20))
    message   = data.get("message", "").strip()

    if not name or not email:
        return jsonify({"success": False, "message": "Nombre y correo son requeridos."}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM rsvp WHERE email=?", (email,)).fetchone()
    if existing:
        db.execute(
            "UPDATE rsvp SET name=?, attending=?, guests=?, message=? WHERE email=?",
            (name, int(attending), guests, message, email),
        )
        db.commit()
        verb = "actualizada"
    else:
        db.execute(
            "INSERT INTO rsvp (name, email, attending, guests, message) VALUES (?,?,?,?,?)",
            (name, email, int(attending), guests, message),
        )
        db.commit()
        verb = "registrada"

    msg = (
        f"¡Gracias, {name}! Tu confirmación fue {verb}. ¡Te esperamos con mucho gusto!"
        if attending
        else f"Gracias por avisarnos, {name}. ¡Te echaremos de menos ese día!"
    )
    return jsonify({"success": True, "message": msg})


# ──────────────────────────────────────────────────────────
#  PANEL NOVIOS
# ──────────────────────────────────────────────────────────
@app.route("/novios/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == WEDDING["admin_user"] and p == WEDDING["admin_pass"]:
            session["logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Usuario o contraseña incorrectos."
    return render_template("admin_login.html", wedding=WEDDING, error=error)


@app.route("/novios/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/novios")
@login_required
def admin_dashboard():
    db    = get_db()
    q     = request.args.get("q", "").strip()
    filt  = request.args.get("filter", "all")

    query = "SELECT * FROM rsvp"
    params = []
    conditions = []
    if q:
        conditions.append("(name LIKE ? OR email LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if filt == "attending":
        conditions.append("attending=1")
    elif filt == "not_attending":
        conditions.append("attending=0")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"

    rows  = db.execute(query, params).fetchall()
    stats = get_stats(db)
    return render_template("admin.html", wedding=WEDDING,
                           guests=rows, stats=stats, q=q, filter=filt)


@app.route("/novios/delete/<int:rsvp_id>", methods=["POST"])
@login_required
def admin_delete(rsvp_id):
    get_db().execute("DELETE FROM rsvp WHERE id=?", (rsvp_id,))
    get_db().commit()
    return jsonify({"success": True})


@app.route("/novios/export")
@login_required
def admin_export():
    import csv, io
    db   = get_db()
    rows = db.execute(
        "SELECT name, email, attending, guests, message, created_at FROM rsvp ORDER BY created_at"
    ).fetchall()
    out = io.StringIO()
    w   = csv.writer(out)
    w.writerow(["Nombre", "Email", "Asiste", "Acompañantes totales", "Mensaje", "Fecha"])
    for r in rows:
        w.writerow([r["name"], r["email"],
                    "Sí" if r["attending"] else "No",
                    r["guests"], r["message"] or "", r["created_at"]])
    return Response(
        out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=invitados.csv"},
    )


# ── Inicializar BD al arrancar (necesario en Render) ──────
init_db()

# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("✅  Base de datos inicializada  →  boda.db")
    print("🌐  Página pública  :  http://localhost:5000")
    print("🔐  Panel de novios :  http://localhost:5000/novios/login")
    print(f"    Usuario: {WEDDING['admin_user']}   Contraseña: {WEDDING['admin_pass']}")
    app.run(debug=True, port=5000)
