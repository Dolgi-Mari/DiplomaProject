import sqlite3

conn = sqlite3.connect('instance/users.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE user ADD COLUMN password_hash VARCHAR(200);")
    print("Колонка password_hash успешно добавлена.")
except sqlite3.OperationalError as e:
    print("Колонка уже существует или ошибка:", e)

conn.commit()
conn.close()