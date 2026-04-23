import sqlite3

conn = sqlite3.connect('instance/users.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE book ADD COLUMN cover_path VARCHAR(300)")
    print("Добавлена колонка cover_path")
except sqlite3.OperationalError as e:
    print("Колонка уже существует или ошибка:", e)

conn.commit()
conn.close()