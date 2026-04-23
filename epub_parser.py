import os
from ebooklib import epub
from bs4 import BeautifulSoup

def get_epub_title(epub_path):
    """
    Извлекает название книги из EPUB-файла.
    Возвращает строку с названием или None, если не удалось.
    """
    try:
        book = epub.read_epub(epub_path)
        # Используем только get_metadata
        metadata = book.get_metadata('DC', 'title')
        if metadata and len(metadata) > 0:
            return metadata[0][0]
        return None
    except Exception as e:
        print(f"Ошибка при получении названия EPUB: {e}")
        return None

def extract_text_from_epub(epub_path, output_html_path, book_id):
    """
    Извлекает текст и изображения из EPUB-файла, сохраняет HTML и копирует картинки.
    book_id нужен для формирования правильного URL к картинкам.
    """
    try:
        book = epub.read_epub(epub_path)
        all_html_pieces = []

        output_dir = os.path.dirname(output_html_path)
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)

        for item in book.get_items():
            if item.get_type() == 9:  # документ (XHTML)
                content = item.get_body_content().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')

                for script in soup(['script', 'style']):
                    script.decompose()

                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src:
                        img_filename = os.path.basename(src)
                        print(f"Найдено изображение: src='{src}', basename='{img_filename}'")
                        found = False
                        for resource in book.get_items():
                            resource_name = resource.get_name()
                            if os.path.basename(resource_name).lower() == img_filename.lower():
                                print(f"  Найден ресурс: {resource_name} (тип {resource.get_type()})")
                                img_data = resource.get_content()
                                img_local_path = os.path.join(images_dir, img_filename)
                                with open(img_local_path, 'wb') as f:
                                    f.write(img_data)
                                print(f"  Изображение сохранено в {img_local_path}")
                                # Формируем URL для доступа через Flask
                                img['src'] = f'/book_images/{book_id}/{img_filename}'
                                found = True
                                break
                        if not found:
                            print(f"  ВНИМАНИЕ: ресурс для {img_filename} не найден!")

                text = str(soup.body) if soup.body else str(soup)
                all_html_pieces.append(text)

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

        os.makedirs(output_dir, exist_ok=True)

        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(full_html)

        print(f"HTML сохранён: {output_html_path}")
        return True
    except Exception as e:
        print(f"Ошибка при обработке EPUB: {e}")
        return False

# Для тестирования, если файл запускают напрямую
if __name__ == "__main__":
    test_epub = "C:/Users/Мария/Desktop/DiplomaProject/test-book-2.epub"
    test_output = "test_output.html"
    if os.path.exists(test_epub):
        success = extract_text_from_epub(test_epub, test_output)
        print(f"Успех: {success}, файл сохранён: {test_output}")
    else:
        print("Укажите правильный путь к EPUB для теста.")

def get_epub_cover(epub_path, cover_save_path):
    """Извлекает обложку из EPUB и сохраняет по указанному пути. Возвращает True/False."""
    try:
        book = epub.read_epub(epub_path)
        # Ищем элемент с типом 'cover' или 'cover-image'
        for item in book.get_items():
            if item.get_type() == epub.ITEM_COVER or 'cover' in item.get_name().lower():
                with open(cover_save_path, 'wb') as f:
                    f.write(item.get_content())
                return True
        # Альтернативный способ: ищем мета-тег cover
        cover_meta = book.get_metadata('OPF', 'cover')
        if cover_meta:
            cover_id = cover_meta[0][0]
            for item in book.get_items():
                if item.get_name() == cover_id or item.id == cover_id:
                    with open(cover_save_path, 'wb') as f:
                        f.write(item.get_content())
                    return True
        return False
    except Exception as e:
        print(f"Ошибка при извлечении обложки EPUB: {e}")
        return False