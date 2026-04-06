import os
import shutil
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from epub_parser import extract_text_from_epub, get_epub_title
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from flask import abort, flash
from flask import send_from_directory, abort
from pdf_parser import extract_text_and_images_from_pdf, get_pdf_title
from docx_parser import extract_text_and_images_from_docx, get_docx_title
from fb2_parser import get_fb2_title, extract_text_and_images_from_fb2
from flask import url_for

from ishihara_data import EXPECTED, PLATE_OPTIONS

# ================== КОНФИГУРАЦИЯ ==================
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Настройки загрузки файлов
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'epub', 'pdf', 'fb2', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# База данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Секретный ключ для сессий (понадобится для регистрации)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # в реальном проекте менять!

# ================== ИНИЦИАЛИЗАЦИЯ ==================
db = SQLAlchemy(app)

# ================== МОДЕЛИ ==================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, default='user1')
    password_hash = db.Column(db.String(200)) 
    
    contrast = db.Column(db.String(20))       # 'high', 'medium', 'low'
    color_vision = db.Column(db.String(20))   # 'normal', 'deutan', 'protan', 'tritan'
    font_pref = db.Column(db.String(20))      # 'small', 'medium', 'large'
    theme_pref = db.Column(db.String(20))     # 'light', 'dark', 'sepia', 'high_contrast'
    
    # НОВЫЕ ПОЛЯ
    light_sensitive = db.Column(db.Boolean, default=False)        # чувствительность к свету (да/нет)
    line_height = db.Column(db.String(20), default='normal')      # 'normal' или 'large'

    # еще новые поля (доработка теста)
    color_blindness_type = db.Column(db.String(20), default='none')   # 'none', 'protanopia', 'deuteranopia', 'tritanopia'
    has_dyslexia = db.Column(db.Boolean, default=False)
    light_sensitivity_level = db.Column(db.String(20), default='low')   # 'low', 'medium', 'high'
    line_width_pref = db.Column(db.String(20), default='medium')        # 'narrow', 'medium', 'wide'

    preferred_font = db.Column(db.String(50), default='Roboto')   # новое поле

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    extracted_html_path = db.Column(db.String(300))  # путь к сгенерированному HTML
    title = db.Column(db.String(200))  # будет извлечено из метаданных
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('books', lazy=True))

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def allowed_file(filename):
    """Проверяет, разрешён ли формат файла."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================== МАРШРУТЫ ==================
@app.context_processor
def inject_user():
    return dict(session=session)

@app.route('/')
def home():
    """Главная страница перенаправляет на тест."""
    return redirect(url_for('test'))

@app.route('/test', methods=['GET', 'POST'])
def test():
    if 'user_id' not in session:
        return redirect(url_for('login', next=url_for('test')))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Старые поля
        font_pref = request.form.get('vision', 'medium')
        # Тема
        theme = request.form.get('theme')
        if not theme:
            theme = request.form.get('contrast', 'normal')
        color_vision = request.form.get('color_vision', 'normal')
        line_height = request.form.get('line_height', 'normal')
        
        # ползунки, светочувствительность
        contrast_sensitivity = int(request.form.get('contrast_sensitivity', 50))
        brightness_preference = int(request.form.get('brightness_preference', 50))
        preferred_line_width_ch = int(request.form.get('preferred_line_width_ch', 66))
        light_sensitivity_level = request.form.get('light_sensitivity_level', 'low')

        # Дислексия и выбор шрифта
        has_dyslexia = request.form.get('dyslexia') == 'yes'
        preferred_font = request.form.get('preferred_font', 'Roboto')   # новое поле

        # Обновляем пользователя
        user.font_pref = font_pref
        user.theme_pref = theme
        user.contrast = theme
        user.color_vision = color_vision
        user.line_height = line_height
        user.contrast_sensitivity = contrast_sensitivity
        user.brightness_preference = brightness_preference
        user.preferred_line_width_ch = preferred_line_width_ch
        user.light_sensitivity_level = light_sensitivity_level
        user.has_dyslexia = has_dyslexia
        user.preferred_font = preferred_font   # сохраняем выбранный шрифт
        
        # Не перезаписываем color_blindness_type, если он уже установлен тестом Ишихары
        
        db.session.commit()
        return redirect(url_for('profile', user_id=user.id))
    
    return render_template('test.html')

@app.route('/profile/<int:user_id>')
def profile(user_id):
    """Профиль пользователя с его настройками и списком книг."""
    
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['user_id'] != user_id:
        return "Доступ запрещён", 403
    
    user = User.query.get_or_404(user_id)
    return render_template('profile.html', user=user)

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Обновляем поля
        user.font_pref = request.form.get('vision', user.font_pref)
        theme = request.form.get('theme')
        if not theme:
            theme = request.form.get('contrast', user.theme_pref)
        user.theme_pref = theme
        user.contrast = theme
        user.color_vision = request.form.get('color_vision', user.color_vision)
        user.font_family = request.form.get('font_family', user.font_family)
        user.line_height = request.form.get('line_height', user.line_height)
        user.contrast_sensitivity = int(request.form.get('contrast_sensitivity', user.contrast_sensitivity or 50))
        user.brightness_preference = int(request.form.get('brightness_preference', user.brightness_preference or 50))
        user.preferred_line_width_ch = int(request.form.get('preferred_line_width_ch', user.preferred_line_width_ch or 66))
        user.has_dyslexia = request.form.get('dyslexia') == 'yes'
        user.dyslexia_font = request.form.get('dyslexia_font') == 'opendyslexic'
        user.light_sensitivity_level = request.form.get('light_sensitivity_level', user.light_sensitivity_level or 'low')
        # Для color_blindness_type не обновляем, его меняет только тест Ишихары
        db.session.commit()
        flash('Настройки обновлены', 'success')
        return redirect(url_for('profile', user_id=user.id))

    return render_template('profile_edit.html', user=user)

@app.route('/upload/<int:user_id>', methods=['GET', 'POST'])
def upload(user_id):
    """
    Загрузка книги.
    Сохраняет файл, создаёт запись в БД.
    + вызов парсер.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['user_id'] != user_id:
        return "Доступ запрещён", 403
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'Нет файла', 400
        file = request.files['file']
        
        if file.filename == '':
            return 'Файл не выбран', 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
            os.makedirs(user_folder, exist_ok=True)
            file_path = os.path.join(user_folder, filename)
            file.save(file_path)
            
            # Определяем расширение файла
            file_ext = filename.rsplit('.', 1)[1].lower()

            # Пытаемся получить настоящее название книги
            book_title = filename  # по умолчанию имя файла
            if file_ext == 'epub':
                try:
                    title_from_meta = get_epub_title(file_path)
                    if title_from_meta:
                        book_title = title_from_meta
                except Exception as e:
                    print(f"Ошибка при получении названия EPUB: {e}")
            elif file_ext == 'pdf':
                try:
                    title_from_meta = get_pdf_title(file_path)
                    if title_from_meta:
                        book_title = title_from_meta
                except Exception as e:
                    print(f"Ошибка при получении названия PDF: {e}")
            elif file_ext == 'docx':
                try:
                    title_from_meta = get_docx_title(file_path)
                    if title_from_meta:
                        book_title = title_from_meta
                except Exception as e:
                    print(f"Ошибка при получении названия DOCX: {e}")
            elif file_ext == 'fb2':
                try:
                    title_from_meta = get_fb2_title(file_path)
                    if title_from_meta:
                        book_title = title_from_meta
                except Exception as e:
                    print(f"Ошибка при получении названия FB2: {e}")

            # Создаём запись в БД с полученным названием
            new_book = Book(
                user_id=user.id,
                filename=filename,
                file_path=file_path,
                title=book_title
            )
            db.session.add(new_book)
            db.session.commit()

            # --- БЛОК ДЛЯ EPUB (парсинг текста) ---
            if file_ext == 'epub':
                html_folder = os.path.join(user_folder, 'html')
                os.makedirs(html_folder, exist_ok=True)
                html_filename = filename.rsplit('.', 1)[0] + '.html'
                html_path = os.path.join(html_folder, html_filename)

                success = extract_text_from_epub(file_path, html_path, new_book.id)
                if success:
                    new_book.extracted_html_path = html_path
                    db.session.commit()
                    print(f"HTML создан: {html_path}")
                else:
                    print(f"Не удалось извлечь текст из EPUB: {filename}")

            # --- БЛОК ДЛЯ PDF ---
            if file_ext == 'pdf':
                html_folder = os.path.join(user_folder, 'html')
                os.makedirs(html_folder, exist_ok=True)
                html_filename = filename.rsplit('.', 1)[0] + '.html'
                html_path = os.path.join(html_folder, html_filename)

                success = extract_text_and_images_from_pdf(file_path, html_path, new_book.id)
                if success:
                    new_book.extracted_html_path = html_path
                    db.session.commit()
                    print(f"HTML создан: {html_path}")
                else:
                    print(f"Не удалось извлечь текст из PDF: {filename}")

            # --- БЛОК ДЛЯ DOCX ---
            if file_ext == 'docx':
                html_folder = os.path.join(user_folder, 'html')
                os.makedirs(html_folder, exist_ok=True)
                html_filename = filename.rsplit('.', 1)[0] + '.html'
                html_path = os.path.join(html_folder, html_filename)

                success = extract_text_and_images_from_docx(file_path, html_path, new_book.id)
                if success:
                    new_book.extracted_html_path = html_path
                    db.session.commit()
                    print(f"HTML создан: {html_path}")
                else:
                    print(f"Не удалось извлечь текст из DOCX: {filename}")
            
            # --- БЛОК ДЛЯ FB2 ---
            if file_ext == 'fb2':
                html_folder = os.path.join(user_folder, 'html')
                os.makedirs(html_folder, exist_ok=True)
                html_filename = filename.rsplit('.', 1)[0] + '.html'
                html_path = os.path.join(html_folder, html_filename)

                success = extract_text_and_images_from_fb2(file_path, html_path, new_book.id)
                if success:
                    new_book.extracted_html_path = html_path
                    db.session.commit()
                    print(f"HTML создан: {html_path}")
                else:
                    print(f"Не удалось извлечь текст из FB2: {filename}")

            return f"Книга {filename} успешно загружена! <a href='/profile/{user.id}'>Вернуться в профиль</a>"
    
    return render_template('upload.html', user=user)

@app.route('/read/<int:book_id>')
def read_book(book_id):
    """Отображает книгу в читалке с учётом настроек пользователя."""
    book = Book.query.get_or_404(book_id)
    user = User.query.get(book.user_id)  # получаем владельца книги

    if not book.extracted_html_path:
        return "Для этой книги ещё не создан HTML.", 400

    html_path = os.path.join(basedir, book.extracted_html_path)
    if not os.path.exists(html_path):
        return f"Файл не найден: {html_path}", 404

    with open(html_path, 'r', encoding='utf-8') as f:
        book_content = f.read()

    # Генерируем классы и стили
    body_classes, style_vars = generate_body_classes(user)

    return render_template('reader.html',
                           book=book,
                           book_content=book_content,
                           user_id=book.user_id,
                           body_classes=body_classes,
                           style_vars=style_vars)
    
@app.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    # Проверка авторизации
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    book = Book.query.get_or_404(book_id)
    
    # Проверка, что книга принадлежит текущему пользователю
    if book.user_id != session['user_id']:
        abort(403)  # доступ запрещён
    
    # Удаляем физические файлы
    try:
        if os.path.exists(book.file_path):
            os.remove(book.file_path)
        if book.extracted_html_path and os.path.exists(book.extracted_html_path):
            # Удаляем папку html, где лежит этот файл
            html_dir = os.path.dirname(book.extracted_html_path)
            if os.path.exists(html_dir):
                shutil.rmtree(html_dir)
    except Exception as e:
        flash(f'Ошибка при удалении файлов: {e}', 'error')
    
    # Удаляем запись из БД
    db.session.delete(book)
    db.session.commit()
    
    flash('Книга успешно удалена', 'success')
    return redirect(url_for('profile', user_id=session['user_id']))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Проверяем, не занято ли имя
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "Пользователь с таким именем уже существует. <a href='/register'>Попробуйте другое имя</a>"
        
        # Создаём нового пользователя с пустыми настройками
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            password_hash=hashed_password,
            # поля настроек пока пустые, их заполнит тест
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Сразу логиним пользователя
        session['user_id'] = new_user.id
        
        return redirect(url_for('test'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Получаем параметр next из URL (если есть)
    next_page = request.args.get('next')
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Также получаем next из скрытого поля формы
        next_page = request.form.get('next') or next_page
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            # Если есть next_page, редиректим туда, иначе в профиль
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('profile', user_id=user.id))
        else:
            return "Неверное имя пользователя или пароль. <a href='/login'>Попробуйте снова</a>"
    
    # GET-запрос: передаём next в шаблон
    return render_template('login.html', next=next_page)
    

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/book_images/<int:book_id>/<path:filename>')
def book_images(book_id, filename):
    """Отдаёт изображения из папки книги."""
    book = Book.query.get_or_404(book_id)
    if not book.extracted_html_path:
        abort(404)
    # Определяем папку, где лежат изображения (рядом с HTML файлом)
    html_dir = os.path.dirname(book.extracted_html_path)
    images_dir = os.path.join(html_dir, 'images')
    # Проверяем существование файла
    if os.path.exists(os.path.join(images_dir, filename)):
        return send_from_directory(images_dir, filename)
    else:
        abort(404)

def generate_body_classes(user):
    """
    Формирует строку классов для body на основе всех параметров пользователя.
    Возвращает также словарь CSS-переменных для инлайн-стилей.
    """
    classes = []
    css_vars = {}

    # 1. Размер шрифта
    font_size = getattr(user, 'font_pref', 'medium')
    classes.append(f'font-{font_size}')

    # 2. Тема (с учётом дальтонизма)
    color_blind = getattr(user, 'color_blindness_type', 'none')
    if color_blind == 'protanopia':
        classes.append('theme-protanopia')
    elif color_blind == 'deuteranopia':
        classes.append('theme-deuteranopia')
    elif color_blind == 'tritanopia':
        classes.append('theme-tritanopia')
    else:
        theme = getattr(user, 'theme_pref', 'normal')
        classes.append(f'theme-{theme}')

    # 3. Шрифт
    preferred_font = getattr(user, 'preferred_font', 'Roboto')
    font_class = f"font-{preferred_font.lower().replace(' ', '-')}"
    classes.append(font_class)

    # 4. Межстрочный интервал
    line_height = getattr(user, 'line_height', 'normal')
    classes.append(f'line-height-{line_height}')

    # 5. Чувствительность к свету (может добавлять класс)
    light_level = getattr(user, 'light_sensitivity_level', 'low')
    if light_level in ('medium', 'high'):
        classes.append('light-sensitive')
    # Для высокой чувствительности можно принудительно включить тёмную тему, но это уже реализовано выше.

    # 6. CSS-переменные для точной настройки
    # Ширина строки
    line_width = getattr(user, 'preferred_line_width_ch', 66)
    css_vars['--line-width'] = f'{line_width}ch'

    # Контраст текста (значение 0..100 -> коэффициент 0.5..2.0)
    contrast_val = getattr(user, 'contrast_sensitivity', 50)
    contrast_factor = 0.5 + (contrast_val / 100) * 1.5
    css_vars['--text-contrast'] = f'{contrast_factor}'

    # Яркость фона (0..100 -> 0.3..1.2)
    brightness_val = getattr(user, 'brightness_preference', 50)
    brightness_factor = 0.3 + (brightness_val / 100) * 0.9
    # Если чувствительность к свету высокая, дополнительно уменьшаем яркость
    if light_level == 'high':
        brightness_factor *= 0.8
    css_vars['--bg-brightness'] = f'{brightness_factor}'

    # Дополнительно можно передать цветовую коррекцию для дальтонизма (если нужно)
    # ...

    # Формируем строку классов и строку стилей
    class_str = ' '.join(classes)
    style_str = '; '.join(f'{k}: {v}' for k, v in css_vars.items())
    return class_str, style_str

@app.route('/ishihara_test', methods=['GET', 'POST'])
def ishihara_test():
    # Только для авторизованных пользователей
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Собираем ответы
        user_answers = {}
        for i in range(1, 39):
            key = f'plate_{i}'
            user_answers[i] = request.form.get(key, 'none')
        
        # Подсчёт совпадений
        scores = {'normal': 0, 'protan': 0, 'deutan': 0}
        for plate_num, expected in EXPECTED.items():
            user_ans = user_answers.get(plate_num)
            if user_ans is None:
                continue
            for typ in scores:
                if expected.get(typ) == user_ans:
                    scores[typ] += 1
        
        diagnosis = max(scores, key=scores.get)
        # Сохраняем в БД
        user.color_blindness_type = diagnosis
        # Для обратной совместимости обновим и старое поле color_vision
        if diagnosis == 'normal':
            user.color_vision = 'normal'
        elif diagnosis == 'protan':
            user.color_vision = 'protan'
        elif diagnosis == 'deutan':
            user.color_vision = 'deutan'
        else:
            user.color_vision = 'unknown'
        db.session.commit()
        
        return render_template('ishihara_result.html', diagnosis=diagnosis, scores=scores)
    
    # GET: показываем форму
    plates = []
    for i in range(1, 39):
        plates.append({
            'number': i,
            'options': PLATE_OPTIONS[i],
            'image': url_for('static', filename=f'ishihara/plate{i}.jpg')
        })
    return render_template('ishihara_test.html', plates=plates)
  
# ================== ЗАПУСК ==================
if __name__ == '__main__':
    app.run(debug=True)