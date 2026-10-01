import sqlite3
import bcrypt
from datetime import datetime

# ============================================
# CRÉATION BASE DE DONNÉES COMPLÈTE
# ============================================

def init_database():
    """Initialise la base de données avec toutes les tables"""
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # ==================== TABLE DETECTIONS ====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        image TEXT NOT NULL,
        confidence REAL NOT NULL,
        statut TEXT DEFAULT 'EN_ATTENTE',
        agent_id INTEGER,
        date_action TEXT,
        FOREIGN KEY (agent_id) REFERENCES users(id)
    )
    """)

    # ==================== TABLE ALERTES ====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alertes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        message TEXT NOT NULL,
        niveau TEXT NOT NULL,
        etat TEXT DEFAULT 'NOUVEAU',
        detection_id INTEGER,
        FOREIGN KEY (detection_id) REFERENCES detections(id)
    )
    """)

    # ==================== TABLE USERS ====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        mot_de_passe TEXT NOT NULL,
        date_creation TEXT,
        dernier_login TEXT,
        actif INTEGER DEFAULT 1
    )
    """)

    # ==================== UTILISATEUR PAR DÉFAUT ====================
    # Vérifier si un admin existe déjà
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='Administrateur'")
    admin_exists = cursor.fetchone()[0]

    if admin_exists == 0:
        # Créer compte admin par défaut
        password = "Admin2024!"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        cursor.execute("""
            INSERT INTO users (nom, email, role, mot_de_passe, date_creation, actif)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "Administrateur CFPD",
            "admin@cfpd-isgd.edu",
            "Administrateur",
            hashed.decode('utf-8'),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            1
        ))
        print("✅ Compte administrateur créé")
        print("   Email: admin@cfpd-isgd.edu")
        print("   Mot de passe: Admin2024!")

    conn.commit()
    conn.close()
    print("✅ Base de données initialisée avec succès!")


if __name__ == "__main__":
    init_database()