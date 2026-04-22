import sqlite3

conn = sqlite3.connect('instance/users.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE user ADD COLUMN ui_theme VARCHAR(20) DEFAULT 'light'")
    print("Добавлена ui_theme")
except sqlite3.OperationalError as e:
    print("ui_theme уже существует или ошибка:", e)

try:
    cursor.execute("ALTER TABLE user ADD COLUMN ui_font_size VARCHAR(20) DEFAULT 'medium'")
    print("Добавлена ui_font_size")
except sqlite3.OperationalError as e:
    print("ui_font_size уже существует или ошибка:", e)

conn.commit()
conn.close()
print("Миграция завершена")