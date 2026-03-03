import os
import PyPDF2
import fitz  # PyMuPDF

def get_pdf_title(pdf_path):
    """
    Извлекает название из PDF-файла (из метаданных).
    Возвращает строку или None.
    """
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            metadata = reader.metadata
            if metadata and '/Title' in metadata:
                return metadata['/Title']
        return None
    except Exception as e:
        print(f"Ошибка при получении названия PDF: {e}")
        return None

def extract_text_and_images_from_pdf(pdf_path, output_html_path, book_id):
    """
    Извлекает текст и изображения из PDF-файла, сохраняет HTML и копирует картинки.
    book_id нужен для формирования правильного URL к картинкам.
    """
    try:
        # Открываем PDF
        doc = fitz.open(pdf_path)
        html_pieces = []

        # Папка для выходного HTML и изображений
        output_dir = os.path.dirname(output_html_path)
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)

        # Проходим по всем страницам
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Извлекаем текст страницы
            text = page.get_text()
            # Оборачиваем текст в абзацы (примитивно)
            paragraphs = text.split('\n\n')
            page_html = ""
            for para in paragraphs:
                if para.strip():
                    page_html += f"<p>{para.replace(chr(10), ' ')}</p>\n"

            # Извлекаем изображения со страницы
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]  # номер объекта
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha < 4:  # можно сохранять как PNG
                    img_filename = f"page{page_num+1}_{img_index+1}.png"
                else:  # CMYK или другое
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_filename = f"page{page_num+1}_{img_index+1}.jpg"
                img_path = os.path.join(images_dir, img_filename)
                pix.save(img_path)
                pix = None

                # Добавляем тег изображения в HTML после текста страницы
                page_html += f'<img src="/book_images/{book_id}/{img_filename}" alt="Иллюстрация со страницы {page_num+1}" style="max-width:100%; margin:10px 0;">\n'

            html_pieces.append(page_html)

        doc.close()

        # Собираем итоговый HTML
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст и изображения из PDF</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; }}
        img {{ display: block; margin: 1em auto; max-width: 90%; height: auto; border: 1px solid #ccc; }}
    </style>
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
        print(f"Ошибка при обработке PDF: {e}")
        return False

# Для тестирования, если файл запускают напрямую
if __name__ == "__main__":
    # Укажи путь к своему PDF-файлу
    test_pdf = "C:/Users/Мария/Desktop/DiplomaProject/test-book.pdf"
    test_output = "./test_pdf_output.html"
    if os.path.exists(test_pdf):
        success = extract_text_and_images_from_pdf(test_pdf, test_output, book_id=999)
        print(f"Успех: {success}, файл сохранён: {test_output}")
    else:
        print(f"Файл не найден: {test_pdf}")