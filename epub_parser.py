import os
from ebooklib import epub
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from ebooklib import epub

def get_epub_title(epub_path):
    """
    Извлекает название книги из EPUB-файла.
    Возвращает строку с названием или None, если не удалось.
    """
    try:
        book = epub.read_epub(epub_path)
        # Название обычно хранится в метаданных Dublin Core
        # В ebooklib оно доступно через book.titles (список)
        if book.titles:
            return book.titles[0]
        # Если нет, пробуем найти в метаданных через get_metadata
        metadata = book.get_metadata('DC', 'title')
        if metadata:
            return metadata[0][0]
        return None
    except Exception as e:
        print(f"Ошибка при получении названия EPUB: {e}")
        return None

def extract_text_from_epub(epub_path, output_html_path):
    """
    Извлекает текст из EPUB-файла и сохраняет его как простой HTML.
    
    :param epub_path: путь к файлу EPUB
    :param output_html_path: путь, куда сохранить результат
    :return: True, если успешно, иначе False
    """
    try:
        # Открываем книгу
        book = epub.read_epub(epub_path)
        
        # Список для сбора всего текста
        all_html_pieces = []
        
        # Проходим по всем элементам книги
        for item in book.get_items():
            # Нас интересуют только документы (тип 9 - документ)
            if item.get_type() == 9:
                # Получаем содержимое как байты, декодируем
                content = item.get_body_content().decode('utf-8', errors='ignore')
                # Парсим HTML
                soup = BeautifulSoup(content, 'html.parser')
                # Удаляем скрипты и стили (они не нужны для текста)
                for script in soup(['script', 'style']):
                    script.decompose()
                # Получаем текст в виде HTML (с сохранением абзацев)
                # Можно взять просто текст, но лучше сохранить абзацы
                text = str(soup.body) if soup.body else str(soup)
                all_html_pieces.append(text)
        
        # Собираем итоговый HTML
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст</title>
</head>
<body>
    {''.join(all_html_pieces)}
</body>
</html>"""
        
        # Создаём папку для выходного файла, если её нет
        output_dir = os.path.dirname(output_html_path)
        if output_dir:  # создаём папку, только если путь не пустой
            os.makedirs(output_dir, exist_ok=True)
        
        # Сохраняем
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        return True
    except Exception as e:
        print(f"Ошибка при обработке EPUB: {e}")
        return False

# Для тестирования, если файл запускают напрямую
if __name__ == "__main__":
    # Замени путь на реальный EPUB-файл
    test_epub = "C:/Users/Мария/Desktop/DiplomaProject/test-book-2.epub"
    test_output = "test_output.html"
    if os.path.exists(test_epub):
        success = extract_text_from_epub(test_epub, test_output)
        print(f"Успех: {success}, файл сохранён: {test_output}")
    else:
        print("Укажите правильный путь к EPUB для теста.")