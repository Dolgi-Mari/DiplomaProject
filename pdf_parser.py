import os
from pdfminer.high_level import extract_text
import PyPDF2

def extract_text_from_pdf(pdf_path, output_html_path):
    """
    Извлекает текст из PDF-файла и сохраняет его как простой HTML.
    
    :param pdf_path: путь к файлу PDF
    :param output_html_path: путь, куда сохранить результат
    :return: True, если успешно, иначе False
    """
    try:
        # Извлекаем текст из PDF
        text = extract_text(pdf_path)
        
        # Разбиваем на абзацы (по пустым строкам)
        paragraphs = text.split('\n\n')
        
        # Оборачиваем каждый абзац в <p>
        html_paragraphs = [f"<p>{p.replace(chr(10), ' ')}</p>" for p in paragraphs if p.strip()]
        
        # Собираем итоговый HTML
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст из PDF</title>
</head>
<body>
    {''.join(html_paragraphs)}
</body>
</html>"""
        
        # Создаём папку для выходного файла, если её нет
        output_dir = os.path.dirname(output_html_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Сохраняем
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        return True
    except Exception as e:
        print(f"Ошибка при обработке PDF: {e}")
        return False

# Для тестирования, если файл запускают напрямую
if __name__ == "__main__":
    # Укажи путь к своему PDF-файлу
    test_pdf = "C:/Users/Мария/Desktop/DiplomaProject/test-book.pdf"  # замени на свой путь
    test_output = "./test_pdf_output.html"
    
    if os.path.exists(test_pdf):
        success = extract_text_from_pdf(test_pdf, test_output)
        print(f"Успех: {success}, файл сохранён: {test_output}")
    else:
        print(f"Файл не найден: {test_pdf}")

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