import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("SELECT id, nom, email, mot_de_passe FROM users")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()