import os

def get_txt_title(txt_path):
    """Извлекает название из TXT-файла (берёт имя файла без расширения)."""
    return os.path.basename(txt_path).rsplit('.', 1)[0]

def extract_text_from_txt(txt_path, output_html_path, book_id):
    """
    Извлекает текст из TXT-файла и сохраняет как HTML.
    """
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        # Разбиваем на строки, оборачиваем в <p>
        lines = text.splitlines()
        html_paragraphs = []
        for line in lines:
            if line.strip():
                html_paragraphs.append(f"<p>{line.strip()}</p>")
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст из TXT</title>
</head>
<body>
    {''.join(html_paragraphs)}
</body>
</html>"""
        os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        return True
    except Exception as e:
        print(f"Ошибка при обработке TXT: {e}")
        return False