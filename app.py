from flask import Flask, render_template, Response, request, redirect, url_for, session, flash, jsonify
import cv2
from ultralytics import YOLO
from datetime import datetime
import os
import time
import smtplib
from email.message import EmailMessage
import sqlite3
import numpy as np
import bcrypt
from functools import wraps

try:
    import pygame
    pygame.mixer.init()

    def play_alarm():
        try:
            pygame.mixer.music.load("alert.wav")
            pygame.mixer.music.set_volume(1.0)
            pygame.mixer.music.play()
        except Exception as e:
            print("Erreur son: " + str(e))

except ImportError:
    def play_alarm():
        print("ALERTE SONORE pygame non disponible")

app = Flask(__name__)
app.secret_key = "votre_cle_secrete_2024"

last_alert_time = 0
ALERT_DELAY = 5
CONF_THRESHOLD = 0.25
detection_active = False

model = YOLO("best.pt", task="detect")
model.fuse = lambda *args, **kwargs: model

camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
camera.set(cv2.CAP_PROP_FPS, 30)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Connectez-vous pour acceder a cette page", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS detections ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "timestamp TEXT NOT NULL,"
        "image TEXT NOT NULL,"
        "confidence REAL NOT NULL,"
        "statut TEXT DEFAULT 'EN_ATTENTE',"
        "agent_id INTEGER,"
        "date_action TEXT)"
    )

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "nom TEXT NOT NULL,"
        "email TEXT UNIQUE NOT NULL,"
        "role TEXT NOT NULL,"
        "mot_de_passe TEXT NOT NULL,"
        "date_creation TEXT,"
        "dernier_login TEXT,"
        "actif INTEGER DEFAULT 1)"
    )

    conn.commit()
    conn.close()

def save_detection(timestamp, image, confidence):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO detections (timestamp, image, confidence, statut) VALUES (?, ?, ?, ?)",
        (timestamp, image, confidence, "EN_ATTENTE")
    )

    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), MAX(timestamp), AVG(confidence) FROM detections")
    total, last, avg = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM detections WHERE statut='EN_ATTENTE'")
    en_attente = cursor.fetchone()[0]

    conn.close()

    return {
        "total_alertes": total if total else 0,
        "derniere_detection": last if last else "Aucune",
        "moyenne_confiance": round(avg * 100, 2) if avg else 0,
        "alertes_en_attente": en_attente if en_attente else 0
    }

def get_detections():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT d.id, d.timestamp, d.image, d.confidence, d.statut, u.nom "
        "FROM detections d "
        "LEFT JOIN users u ON d.agent_id = u.id "
        "ORDER BY d.id DESC"
    )

    rows = cursor.fetchall()
    conn.close()
    return rows

def verify_user(email, password):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, nom, email, role, mot_de_passe FROM users WHERE email=? AND actif=1",
        (email,)
    )

    user = cursor.fetchone()
    conn.close()

    if user:
        user_id, nom, user_email, role, hashed_password = user
        if bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8")):
            return {"id": user_id, "nom": nom, "email": user_email, "role": role}

    return None

def update_last_login(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET dernier_login=? WHERE id=?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id)
    )

    conn.commit()
    conn.close()

def envoyer_email(image_path, confidence, timestamp):
    try:
        EMAIL_SENDER = "amaryldoekassi@gmail.com"
        EMAIL_PASSWORD = "bjhg xjzg uykl vyje"
        EMAIL_RECEIVER = "amaryldoekassi@gmail.com"

        msg = EmailMessage()
        msg["Subject"] = "ALERTE SECURITE - ARME DETECTEE"
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER

        contenu = (
            "ALERTE SECURITE - CFPD-ISGD\n\n"
            "Une arme a ete detectee et VALIDEE par un agent.\n\n"
            "Date : " + str(timestamp) + "\n"
            "Confiance IA : " + str(round(confidence * 100, 2)) + "%\n\n"
            "Intervention recommandee immediatement.\n\n"
            "---\n"
            "Systeme de Detection Automatique d Armes\n"
            "CFPD-ISGD - BTS GL"
        )

        msg.set_content(contenu)

        with open(image_path, "rb") as f:
            file_data = f.read()
            msg.add_attachment(file_data, maintype="image", subtype="jpeg", filename="detection.jpg")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)

        return True

    except Exception as e:
        print("Erreur envoi email: " + str(e))
        return False

# ============================================
# FONCTION GENERATION FLUX VIDEO
# ============================================

def gen_frames():
    global last_alert_time, detection_active
    frame_count = 0

    while True:
        if not detection_active:
            image_path = "static/images/paused.jpg"
            if os.path.exists(image_path):
                blank = cv2.imread(image_path)
            else:
                blank = None

            if blank is None:
                blank = np.zeros((480, 640, 3), dtype="uint8")
                cv2.putText(blank, "DETECTION EN PAUSE", (120, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            ret, buffer = cv2.imencode(".jpg", blank)
            frame_bytes = buffer.tobytes()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(0.5)
            continue

        success, frame = camera.read()
        if not success:
            print("Erreur lecture camera")
            break

        frame_count += 1
        if frame_count % 2 != 0:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
            ret, buffer = cv2.imencode(".jpg", frame, encode_param)
            if ret:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
            time.sleep(0.01)
            continue

        results = model(frame, conf=0.1, iou=0.4, verbose=False)

        if len(results[0].boxes) > 0:
            for box in results[0].boxes:
                confidence = float(box.conf[0])
                if confidence > CONF_THRESHOLD:
                    current_time = time.time()
                    if current_time - last_alert_time > ALERT_DELAY:
                        last_alert_time = current_time
                        play_alarm()
                        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        os.makedirs("static/captures", exist_ok=True)
                        os.makedirs("logs", exist_ok=True)

                        image_name = "arme_" + now + ".jpg"
                        image_save_path = "static/captures/" + image_name
                        cv2.imwrite(image_save_path, frame)
                        save_detection(now, "captures/" + image_name, confidence)

                        with open("logs/events.txt", "a") as f:
                            f.write(now + " - ARME DETECTEE (conf: " + str(round(confidence, 2)) + ")\n")

                        cv2.putText(frame, "ALERTE ARME DETECTEE", (30, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

        annotated_frame = results[0].plot()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
        ret, buffer = cv2.imencode(".jpg", annotated_frame, encode_param)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.01)

# ============================================
# ROUTES PUBLIQUES
# ============================================

@app.route("/")
def index():
    stats = get_stats()
    return render_template("index.html", detection_active=detection_active, **stats)

@app.route("/video")
def video():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/detect_image", methods=["POST"])
def detect_image():
    # Vérifier qu'une image a été envoyée
    if "image" not in request.files:
        flash("Aucune image sélectionnée", "error")
        return redirect(url_for("index"))

    file = request.files["image"]

    # Vérifier que le fichier n'est pas vide
    if file.filename == "":
        flash("Aucune image sélectionnée", "error")
        return redirect(url_for("index"))

    # Créer le dossier de résultats
    os.makedirs("static/demo", exist_ok=True)

    # Nom temporaire de l'image originale
    input_path = os.path.join("static/demo", "image_test.jpg")

    # Sauvegarder l'image
    file.save(input_path)

    try:
        # Lire l'image
        image = cv2.imread(input_path)

        if image is None:
            flash("Impossible de lire cette image", "error")
            return redirect(url_for("index"))

        # Effectuer la détection avec YOLO
        results = model(image, conf=0.25, iou=0.4, verbose=False)

        # Image annotée avec les détections
        annotated_image = results[0].plot()

        # Sauvegarder le résultat
        output_path = os.path.join("static/demo", "resultat.jpg")
        cv2.imwrite(output_path, annotated_image)

        # Compter les détections
        detections_count = len(results[0].boxes)

        return render_template(
            "resultat.html",
            image_result="/static/demo/resultat.jpg",
            detections_count=detections_count
        )

    except Exception as e:
        print("Erreur détection image :", e)
        flash("Une erreur est survenue pendant la détection", "error")
        return redirect(url_for("index"))
# ============================================
# ROUTES AUTHENTIFICATION
# ============================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = verify_user(email, password)
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["nom"]
            session["user_role"] = user["role"]
            session["user_email"] = user["email"]
            update_last_login(user["id"])
            flash("Bienvenue " + user["nom"] + " !", "success")
            return redirect(url_for("agent"))
        else:
            flash("Email ou mot de passe incorrect", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Vous etes deconnecte", "info")
    return redirect(url_for("index"))

# ============================================
# ROUTES PROTEGEES (AGENT)
# ============================================

@app.route("/agent")
@login_required
def agent():
    stats = get_stats()
    return render_template(
        "agent.html",
        user_name=session.get("user_name"),
        detection_active=detection_active,
        **stats
    )

@app.route("/historique")
@login_required
def historique():
    detections = get_detections()
    stats = get_stats()
    return render_template(
        "historique.html",
        detections=detections,
        user_name=session.get("user_name"),
        **stats
    )

# ============================================
# ROUTES ACTIONS (AGENT)
# ============================================

@app.route("/start_detection", methods=["POST"])
@login_required
def start_detection():
    global detection_active
    detection_active = True
    return jsonify({"status": "success", "message": "Detection demarree"})

@app.route("/stop_detection", methods=["POST"])
@login_required
def stop_detection():
    global detection_active
    detection_active = False
    return jsonify({"status": "success", "message": "Detection arretee"})

@app.route("/valider_alerte", methods=["POST"])
@login_required
def valider_alerte():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, timestamp, image, confidence FROM detections "
        "WHERE statut='EN_ATTENTE' ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()

    if row:
        id_det, timestamp, image_path, confidence = row
        full_image_path = "static/" + image_path
        email_sent = envoyer_email(full_image_path, confidence, timestamp)
        cursor.execute(
            "UPDATE detections SET statut='VALIDEE', agent_id=?, date_action=? WHERE id=?",
            (session["user_id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id_det)
        )
        conn.commit()
        conn.close()
        if email_sent:
            return jsonify({"status": "success", "message": "Alerte validee et email envoye"})
        else:
            return jsonify({"status": "warning", "message": "Alerte validee mais email non envoye"})

    conn.close()
    return jsonify({"status": "error", "message": "Aucune alerte en attente"})

@app.route("/rejeter_alerte", methods=["POST"])
@login_required
def rejeter_alerte():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE detections SET statut='REJETEE', agent_id=?, date_action=? "
        "WHERE id = (SELECT id FROM detections WHERE statut='EN_ATTENTE' ORDER BY id DESC LIMIT 1)",
        (session["user_id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Alerte rejetee"})

@app.route("/supprimer/<int:id>", methods=["POST"])
@login_required
def supprimer(id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT image FROM detections WHERE id=?", (id,))
    row = cursor.fetchone()
    if row:
        image_path = "static/" + row[0]
        if os.path.exists(image_path):
            os.remove(image_path)
        cursor.execute("DELETE FROM detections WHERE id=?", (id,))
        conn.commit()
    conn.close()
    return redirect(url_for("historique"))

# ============================================
# API STATISTIQUES (AJAX)
# ============================================

@app.route("/api/stats")
def api_stats():
    stats = get_stats()
    return jsonify(stats)

# ============================================
# INITIALISATION ET LANCEMENT
# ============================================

if __name__ == "__main__":
    init_db()
    os.makedirs("static/captures", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("static/images", exist_ok=True)

    print("==================================================")
    print(" SYSTEME DE DETECTION D ARMES - CFPD-ISGD")
    print("==================================================")
    print("Serveur Flask demarre")
    print("URL: http://127.0.0.1:5000")
    print("==================================================")

    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)