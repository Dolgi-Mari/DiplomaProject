import sqlite3

conn = sqlite3.connect('instance/users.db')
cursor = conn.cursor()

# Добавляем новое поле preferred_font
try:
    cursor.execute("ALTER TABLE user ADD COLUMN preferred_font VARCHAR(50) DEFAULT 'Roboto'")
    print("Добавлено preferred_font")
except sqlite3.OperationalError as e:
    print("preferred_font уже существует или ошибка:", e)

# Удаляем старые поля (если они есть) – в SQLite нельзя удалить колонку напрямую, но можно их просто игнорировать. Оставим как есть, но в коде не будем использовать.
# Для чистоты можно создать новую таблицу, но это сложно. Пока просто проигнорируем.

conn.commit()
conn.close()
print("Миграция завершена")