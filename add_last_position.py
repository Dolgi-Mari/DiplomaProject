import sqlite3

conn = sqlite3.connect('instance/users.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE book ADD COLUMN last_position INTEGER DEFAULT 0")
    print("Колонка last_position добавлена в таблицу book")
except sqlite3.OperationalError as e:
    print("Колонка уже существует или ошибка:", e)

conn.commit()
conn.close()