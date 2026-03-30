import sqlite3

conn = sqlite3.connect('instance/users.db')
cursor = conn.cursor()

# Добавляем новые колонки, если их нет
try:
    cursor.execute("ALTER TABLE user ADD COLUMN color_blindness_type VARCHAR(20) DEFAULT 'none'")
    print("Добавлена color_blindness_type")
except sqlite3.OperationalError as e:
    print("color_blindness_type уже существует или ошибка:", e)

try:
    cursor.execute("ALTER TABLE user ADD COLUMN has_dyslexia BOOLEAN DEFAULT 0")
    print("Добавлена has_dyslexia")
except sqlite3.OperationalError as e:
    print("has_dyslexia уже существует или ошибка:", e)

try:
    cursor.execute("ALTER TABLE user ADD COLUMN dyslexia_font BOOLEAN DEFAULT 0")
    print("Добавлена dyslexia_font")
except sqlite3.OperationalError as e:
    print("dyslexia_font уже существует или ошибка:", e)

try:
    cursor.execute("ALTER TABLE user ADD COLUMN light_sensitivity_level VARCHAR(20) DEFAULT 'low'")
    print("Добавлена light_sensitivity_level")
except sqlite3.OperationalError as e:
    print("light_sensitivity_level уже существует или ошибка:", e)

try:
    cursor.execute("ALTER TABLE user ADD COLUMN line_width_pref VARCHAR(20) DEFAULT 'medium'")
    print("Добавлена line_width_pref")
except sqlite3.OperationalError as e:
    print("line_width_pref уже существует или ошибка:", e)

conn.commit()
conn.close()
print("Миграция завершена")