import sqlite3
import bcrypt

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

password = "admin123"

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

cursor.execute("""
INSERT INTO users (nom, email, mot_de_passe, role, actif)
VALUES (?, ?, ?, ?, ?)
""", ("Admin", "admin@test.com", hashed.decode('utf-8'), "admin", 1))

conn.commit()
conn.close()

print("Utilisateur créé avec succès")