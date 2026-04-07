import os
from striprtf.striprtf import rtf_to_text

def get_rtf_title(rtf_path):
    """Извлекает название из RTF-файла (имя файла без расширения)."""
    return os.path.basename(rtf_path).rsplit('.', 1)[0]

def extract_text_from_rtf(rtf_path, output_html_path, book_id):
    """
    Извлекает текст из RTF-файла и сохраняет как HTML.
    """
    try:
        with open(rtf_path, 'r', encoding='utf-8', errors='ignore') as f:
            rtf_content = f.read()
        text = rtf_to_text(rtf_content)
        lines = text.splitlines()
        html_paragraphs = []
        for line in lines:
            if line.strip():
                html_paragraphs.append(f"<p>{line.strip()}</p>")
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст из RTF</title>
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
        print(f"Ошибка при обработке RTF: {e}")
        return False