import os
import zipfile
import shutil
import tempfile
from docx import Document
from lxml import etree

def get_docx_title(docx_path):
    """Извлекает название из .docx файла."""
    try:
        doc = Document(docx_path)
        return doc.core_properties.title
    except Exception as e:
        print(f"Ошибка при получении названия DOCX: {e}")
        return None

def extract_text_and_images_from_docx(docx_path, output_html_path, book_id):
    """
    Извлекает текст и изображения из .docx, сохраняет HTML и копирует картинки.
    """
    temp_dir = None
    try:
        # Распаковываем docx во временную папку
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Папка для изображений в выходной директории
        output_dir = os.path.dirname(output_html_path)
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)

        # Копируем все изображения из word/media в images_dir
        media_dir = os.path.join(temp_dir, 'word', 'media')
        image_map = {}
        if os.path.exists(media_dir):
            for fname in os.listdir(media_dir):
                src = os.path.join(media_dir, fname)
                dst = os.path.join(images_dir, fname)
                shutil.copy2(src, dst)
                image_map[fname] = fname
        print("ОТЛАДКА: скопированные изображения:", list(image_map.keys()))

        # Парсим document.xml
        doc_xml_path = os.path.join(temp_dir, 'word', 'document.xml')
        if not os.path.exists(doc_xml_path):
            raise Exception("document.xml not found")

        tree = etree.parse(doc_xml_path)
        root = tree.getroot()
        namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
            'pkg': 'http://schemas.openxmlformats.org/package/2006/relationships'  # для файла отношений
        }

        # Ищем document.xml.rels
        rels_path = os.path.join(temp_dir, 'word', '_rels', 'document.xml.rels')
        rels_dict = {}
        if os.path.exists(rels_path):
            print(f"Найден файл отношений: {rels_path}")
            rels_tree = etree.parse(rels_path)
            rels_root = rels_tree.getroot()
            # Ищем Relationship с правильным пространством имён
            for rel in rels_root.findall(f'.//{{{namespaces["pkg"]}}}Relationship'):
                rel_id = rel.get('Id')
                target = rel.get('Target')
                if rel_id and target:
                    rels_dict[rel_id] = target
            print("ОТЛАДКА: rels_dict =", rels_dict)
        else:
            print("ВНИМАНИЕ: файл отношений не найден")

        # Функция для обработки одного абзаца
        def process_paragraph(p_element):
            html = []
            for run in p_element.findall(f'.//w:r', namespaces):
                # Текст
                for t in run.findall(f'.//w:t', namespaces):
                    if t.text:
                        html.append(t.text)
                # Изображения
                drawing = run.find(f'.//w:drawing', namespaces)
                if drawing is not None:
                    blip = drawing.find(f'.//a:blip', namespaces)
                    if blip is not None:
                        rel_id = blip.get(f'{{{namespaces["r"]}}}embed')
                        if rel_id in rels_dict:
                            target = rels_dict[rel_id]
                            img_filename = os.path.basename(target)
                            if img_filename in image_map:
                                html.append(f'<img src="/book_images/{book_id}/{img_filename}" alt="Иллюстрация" style="max-width:100%; margin:10px 0;">')
                            else:
                                print(f"ОТЛАДКА: {img_filename} не найден в image_map")
                        else:
                            print(f"ОТЛАДКА: rel_id {rel_id} не найден в rels_dict")
            if html:
                return '<p>' + ''.join(html) + '</p>'
            return None

        # Функция для обработки таблицы
        def process_table(tbl_element):
            html = ['<table border="1" style="border-collapse: collapse; width:100%;">']
            for row in tbl_element.findall(f'.//w:tr', namespaces):
                html.append('<tr>')
                for cell in row.findall(f'.//w:tc', namespaces):
                    cell_content = []
                    for cell_p in cell.findall(f'.//w:p', namespaces):
                        p_text = []
                        for t in cell_p.findall(f'.//w:t', namespaces):
                            if t.text:
                                p_text.append(t.text)
                        if p_text:
                            cell_content.append(' '.join(p_text))
                    html.append(f'<td>{"<br>".join(cell_content)}</td>')
                html.append('</tr>')
            html.append('</table>')
            return ''.join(html)

        # Проходим по элементам body
        body = root.find(f'.//w:body', namespaces)
        if body is None:
            raise Exception("No body found in document")

        html_pieces = []
        for element in body.iterchildren():
            tag = etree.QName(element).localname
            if tag == 'p':
                para = process_paragraph(element)
                if para:
                    html_pieces.append(para)
            elif tag == 'tbl':
                html_pieces.append(process_table(element))

        # Собираем HTML
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Извлечённый текст из DOCX</title>
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
        print(f"Ошибка при обработке DOCX: {e}")
        return False
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_docx = "C:/Users/Мария/Desktop/DiplomaProject/test.docx"
    test_output = "./test_docx_output.html"
    if os.path.exists(test_docx):
        success = extract_text_and_images_from_docx(test_docx, test_output, book_id=999)
        print(f"Успех: {success}, файл сохранён: {test_output}")
    else:
        print(f"Файл не найден: {test_docx}")

def get_docx_cover(docx_path, cover_save_path):
    """
    Извлекает первое изображение из DOCX и сохраняет его как обложку.
    Возвращает True, если изображение найдено и сохранено.
    """
    import zipfile
    import shutil
    import tempfile
    try:
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        media_dir = os.path.join(temp_dir, 'word', 'media')
        if os.path.exists(media_dir):
            images = [f for f in os.listdir(media_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
            if images:
                # Берём первый найденный файл (можно отсортировать по имени)
                img_file = images[0]
                src = os.path.join(media_dir, img_file)
                shutil.copy2(src, cover_save_path)
                return True
        return False
    except Exception as e:
        print(f"Ошибка при извлечении обложки из DOCX: {e}")
        return False
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)