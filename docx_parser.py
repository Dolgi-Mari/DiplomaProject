import os
from docx import Document

def get_docx_title(docx_path):
    """
    Извлекает название из .docx файла (из свойств документа).
    Возвращает строку или None.
    """
    try:
        doc = Document(docx_path)
        # Пытаемся получить title из core properties
        title = doc.core_properties.title
        if title:
            return title
        return None
    except Exception as e:
        print(f"Ошибка при получении названия DOCX: {e}")
        return None

def extract_text_from_docx(docx_path, output_html_path, book_id):
    """
    Извлекает текст из .docx файла и сохраняет как HTML.
    (Изображения пока не обрабатываем)
    """
    try:
        doc = Document(docx_path)
        paragraphs = []

        # Извлекаем текст из всех абзацев
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(f"<p>{para.text}</p>")

        # Извлекаем текст из таблиц (если есть)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(f"<p>{cell.text}</p>")

        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст из DOCX</title>
</head>
<body>
    {''.join(paragraphs)}
</body>
</html>"""

        output_dir = os.path.dirname(output_html_path)
        os.makedirs(output_dir, exist_ok=True)

        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(full_html)

        print(f"HTML сохранён: {output_html_path}")
        return True
    except Exception as e:
        print(f"Ошибка при обработке DOCX: {e}")
        return False

# Для тестирования напрямую
if __name__ == "__main__":
    test_docx = "C:/Users/Мария/Desktop/DiplomaProject/test.docx"
    test_output = "./test_docx_output.html"
    if os.path.exists(test_docx):
        success = extract_text_from_docx(test_docx, test_output, book_id=999)
        print(f"Успех: {success}, файл сохранён: {test_output}")
    else:
        print(f"Файл не найден: {test_docx}")