import sqlite3

conn = sqlite3.connect('instance/users.db')
cursor = conn.cursor()

# Добавляем новую колонку
try:
    cursor.execute("ALTER TABLE user ADD COLUMN font_size_px INTEGER DEFAULT 16")
    print("Добавлена колонка font_size_px")
except sqlite3.OperationalError as e:
    print("Колонка уже существует или ошибка:", e)

# Переносим старые значения font_pref в font_size_px
cursor.execute("UPDATE user SET font_size_px = 14 WHERE font_pref = 'small'")
cursor.execute("UPDATE user SET font_size_px = 16 WHERE font_pref = 'medium' OR font_pref IS NULL")
cursor.execute("UPDATE user SET font_size_px = 20 WHERE font_pref = 'large'")
conn.commit()
conn.close()
print("Миграция завершена")