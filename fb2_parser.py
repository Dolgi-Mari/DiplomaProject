import os
import base64
from bs4 import BeautifulSoup

def get_fb2_title(fb2_path):
    """
    Извлекает название книги из FB2-файла.
    Возвращает строку или None.
    """
    try:
        with open(fb2_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'xml')
        title_tag = soup.find('book-title')
        if title_tag:
            return title_tag.get_text(strip=True)
        return None
    except Exception as e:
        print(f"Ошибка при получении названия FB2: {e}")
        return None

def extract_text_and_images_from_fb2(fb2_path, output_html_path, book_id):
    """
    Извлекает текст и изображения из FB2-файла, сохраняет HTML и копирует картинки.
    book_id нужен для формирования правильного URL к картинкам.
    """
    try:
        with open(fb2_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'xml')

        # Папка для выходного HTML и изображений
        output_dir = os.path.dirname(output_html_path)
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)

        # Собираем текст из всех абзацев (<p>)
        body = soup.find('body')
        html_pieces = []

        if body:
            # Проходим по всем элементам внутри body
            for elem in body.children:
                if elem.name == 'section':
                    # Разделы могут содержать заголовки и абзацы
                    for child in elem.children:
                        if child.name == 'title':
                            html_pieces.append(f"<h2>{child.get_text(strip=True)}</h2>")
                        elif child.name == 'p':
                            html_pieces.append(f"<p>{child.get_text(strip=True)}</p>")
                elif elem.name == 'p':
                    html_pieces.append(f"<p>{elem.get_text(strip=True)}</p>")

        # Обрабатываем бинарные данные (изображения)
        binaries = soup.find_all('binary')
        for binary in binaries:
            binary_id = binary.get('id')
            content_type = binary.get('content-type', '')
            data = binary.get_text(strip=True)  # base64 строка
            if data:
                # Определяем расширение по content-type
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                elif 'png' in content_type:
                    ext = 'png'
                elif 'gif' in content_type:
                    ext = 'gif'
                else:
                    ext = 'bin'  # на всякий случай

                img_filename = f"{binary_id}.{ext}"
                img_path = os.path.join(images_dir, img_filename)

                # Декодируем base64 и сохраняем
                try:
                    img_data = base64.b64decode(data)
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                    print(f"Изображение сохранено: {img_path}")
                except Exception as e:
                    print(f"Ошибка при сохранении изображения {binary_id}: {e}")

                # Заменяем в тексте ссылки на изображения (обычно <image l:href="#id">)
                # Но пока не заморачиваемся, т.к. в HTML мы их не вставляем автоматически.
                # Можно потом доработать.

        # Простой поиск изображений в тексте: если есть <image>, добавляем тег img
        for img_tag in soup.find_all('image'):
            href = img_tag.get('l:href') or img_tag.get('href')
            if href and href.startswith('#'):
                img_id = href[1:]
                ext = 'jpg'  # по умолчанию, но можно уточнить
                img_filename = f"{img_id}.{ext}"
                # Проверим, есть ли такой файл в images_dir
                # (мы уже сохранили все бинарники, но расширение может не совпадать)
                # Для простоты будем искать файл с таким id, независимо от расширения
                found = False
                for fname in os.listdir(images_dir):
                    if fname.startswith(img_id):
                        img_filename = fname
                        found = True
                        break
                if found:
                    html_pieces.append(f'<img src="/book_images/{book_id}/{img_filename}" alt="Иллюстрация" style="max-width:100%; margin:10px 0;">')

        # Собираем итоговый HTML
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст из FB2</title>
</head>
<body>
    {''.join(html_pieces)}
</body>
</html>"""

        os.makedirs(output_dir, exist_ok=True)
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(full_html)

        print(f"HTML сохранён: {output_html_path}")
        return True
    except Exception as e:
        print(f"Ошибка при обработке FB2: {e}")
        return False

# Для тестирования напрямую
if __name__ == "__main__":
    test_fb2 = "C:/Users/Мария/Desktop/DiplomaProject/test.fb2"
    test_output = "./test_fb2_output.html"
    if os.path.exists(test_fb2):
        success = extract_text_and_images_from_fb2(test_fb2, test_output, book_id=999)
        print(f"Успех: {success}, файл сохранён: {test_output}")
    else:
        print(f"Файл не найден: {test_fb2}")

def get_fb2_cover(fb2_path, cover_save_path):
    """Извлекает обложку из FB2 (тег coverpage) и сохраняет."""
    try:
        with open(fb2_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        soup = BeautifulSoup(content, 'xml')
        coverpage = soup.find('coverpage')
        if coverpage:
            image = coverpage.find('image')
            if image:
                href = image.get('l:href') or image.get('href')
                if href and href.startswith('#'):
                    binary_id = href[1:]
                    binary = soup.find('binary', id=binary_id)
                    if binary:
                        data = binary.get_text(strip=True)
                        img_data = base64.b64decode(data)
                        with open(cover_save_path, 'wb') as f:
                            f.write(img_data)
                        return True
        return False
    except Exception as e:
        print(f"Ошибка при извлечении обложки FB2: {e}")
        return False