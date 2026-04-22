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
from flask import send_from_directory
from pdf_parser import extract_text_and_images_from_pdf, get_pdf_title
from docx_parser import extract_text_and_images_from_docx, get_docx_title
from fb2_parser import get_fb2_title, extract_text_and_images_from_fb2
from txt_parser import extract_text_from_txt, get_txt_title
from rtf_parser import extract_text_from_rtf, get_rtf_title
from ishihara_data import EXPECTED, PLATE_OPTIONS

# ================== КОНФИГУРАЦИЯ ==================
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Настройки загрузки файлов
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'epub', 'pdf', 'fb2', 'docx', 'txt', 'rtf'}
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
    line_height = db.Column(db.String(20), default='normal')      # 'normal' или 'large'
    color_blindness_type = db.Column(db.String(20), default='none')   # 'none', 'protanopia', 'deuteranopia', 'tritanopia'
    has_dyslexia = db.Column(db.Boolean, default=False)
    light_sensitivity_level = db.Column(db.String(20), default='low')   # 'low', 'medium', 'high'
    preferred_font = db.Column(db.String(50), default='Roboto') 
    contrast_sensitivity = db.Column(db.Integer, default=50)
    brightness_preference = db.Column(db.Integer, default=50)
    preferred_line_width_ch = db.Column(db.Integer, default=66)

    ui_theme = db.Column(db.String(20), default='light')      # 'light', 'dark', 'mono'
    ui_font_size = db.Column(db.String(20), default='medium') # 'small', 'medium', 'large'

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
    last_position = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref=db.backref('books', lazy=True))

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def allowed_file(filename):
    """Проверяет, разрешён ли формат файла."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================== МАРШРУТЫ ==================
@app.context_processor
def inject_ui_settings():
    ui_theme = 'light'
    ui_font_size = 'medium'
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            ui_theme = getattr(user, 'ui_theme', 'light')
            ui_font_size = getattr(user, 'ui_font_size', 'medium')
    return dict(ui_theme=ui_theme, ui_font_size=ui_font_size)

@app.route('/')
def home():
    return render_template('index.html')

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
        user.preferred_font = preferred_font

        # Синхронизация color_blindness_type с color_vision
        if color_vision == 'normal':
            user.color_blindness_type = 'none'
        elif color_vision == 'deutan':
            user.color_blindness_type = 'deuteranopia'
        elif color_vision == 'protan':
            user.color_blindness_type = 'protanopia'
        elif color_vision == 'tritan':
            user.color_blindness_type = 'tritanopia'
        
        db.session.commit()
        return redirect(url_for('profile', user_id=user.id))
    
    return render_template('test.html')

@app.route('/profile/<int:user_id>')
def profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['user_id'] != user_id:
        return "Доступ запрещён", 403
    user = User.query.get_or_404(user_id)
    
    # Пагинация книг (10 на страницу)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    books_pagination = Book.query.filter_by(user_id=user.id).order_by(Book.uploaded_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('profile.html', user=user, books=books_pagination)

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Изменение имени пользователя
        new_username = request.form.get('username')
        if new_username and new_username != user.username:
            # Проверка на уникальность
            existing = User.query.filter_by(username=new_username).first()
            if existing and existing.id != user.id:
                flash('Имя пользователя уже занято', 'error')
            else:
                user.username = new_username
                flash('Имя пользователя обновлено', 'success')
        
        # Изменение пароля
        new_password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        if new_password:
            if new_password == password_confirm:
                user.password_hash = generate_password_hash(new_password)
                flash('Пароль обновлён', 'success')
            else:
                flash('Пароли не совпадают', 'error')
        
        # Обновление настроек чтения (как и раньше)
        user.font_pref = request.form.get('vision', user.font_pref)
        theme = request.form.get('theme')
        if not theme:
            theme = request.form.get('contrast', user.theme_pref)
        user.theme_pref = theme
        user.contrast = theme
        user.color_vision = request.form.get('color_vision', user.color_vision)
        # Синхронизация
        cv = user.color_vision
        if cv == 'normal':
            user.color_blindness_type = 'none'
        elif cv == 'deutan':
            user.color_blindness_type = 'deuteranopia'
        elif cv == 'protan':
            user.color_blindness_type = 'protanopia'
        elif cv == 'tritan':
            user.color_blindness_type = 'tritanopia'
        user.line_height = request.form.get('line_height', user.line_height)
        user.contrast_sensitivity = int(request.form.get('contrast_sensitivity', user.contrast_sensitivity or 50))
        user.brightness_preference = int(request.form.get('brightness_preference', user.brightness_preference or 50))
        user.preferred_line_width_ch = int(request.form.get('preferred_line_width_ch', user.preferred_line_width_ch or 66))
        user.has_dyslexia = request.form.get('dyslexia') == 'yes'
        user.light_sensitivity_level = request.form.get('light_sensitivity_level', user.light_sensitivity_level or 'low')
        user.preferred_font = request.form.get('preferred_font', user.preferred_font or 'Roboto')
        
        db.session.commit()
        return redirect(url_for('profile', user_id=user.id))

    return render_template('profile_edit.html', user=user)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # сохраняем настройки
        user.ui_theme = request.form.get('ui_theme', 'light')
        user.ui_font_size = request.form.get('ui_font_size', 'medium')
        db.session.commit()
        flash('Настройки интерфейса сохранены', 'success')
        next_page = request.form.get('next')
        if next_page:
            return redirect(next_page)
        else:
            return redirect(url_for('profile', user_id=user.id))
    
    return render_template('settings.html', user=user)

def process_uploaded_file(file, user, user_folder):
    """
    Обрабатывает один загруженный файл: сохраняет, извлекает метаданные,
    создаёт запись в БД, вызывает парсер.
    Возвращает (success, message) – успех и сообщение.
    """
    filename = secure_filename(file.filename)
    file_path = os.path.join(user_folder, filename)
    file.save(file_path)
    
    # Определяем расширение
    file_ext = filename.rsplit('.', 1)[1].lower()
    
    # Пытаемся получить название книги
    book_title = filename  # по умолчанию
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
    elif file_ext == 'txt':
        try:
            title_from_meta = get_txt_title(file_path)
            if title_from_meta:
                book_title = title_from_meta
        except Exception as e:
            print(f"Ошибка при получении названия TXT: {e}")
    elif file_ext == 'rtf':
        try:
            title_from_meta = get_rtf_title(file_path)
            if title_from_meta:
                book_title = title_from_meta
            # Предупреждение о возможных проблемах с таблицами/изображениями
            flash(f'Файл {filename} (RTF) может содержать некорректно отображаемые таблицы или изображения.', 'warning')
        except Exception as e:
            print(f"Ошибка при получении названия RTF: {e}")

    # Создаём запись в БД
    new_book = Book(
        user_id=user.id,
        filename=filename,
        file_path=file_path,
        title=book_title
    )
    db.session.add(new_book)
    db.session.commit()

    # --- Вызов парсеров ---
    success = False
    if file_ext == 'epub':
        html_folder = os.path.join(user_folder, 'html')
        os.makedirs(html_folder, exist_ok=True)
        html_filename = filename.rsplit('.', 1)[0] + '.html'
        html_path = os.path.join(html_folder, html_filename)
        success = extract_text_from_epub(file_path, html_path, new_book.id)
    elif file_ext == 'pdf':
        html_folder = os.path.join(user_folder, 'html')
        os.makedirs(html_folder, exist_ok=True)
        html_filename = filename.rsplit('.', 1)[0] + '.html'
        html_path = os.path.join(html_folder, html_filename)
        success = extract_text_and_images_from_pdf(file_path, html_path, new_book.id)
    elif file_ext == 'docx':
        html_folder = os.path.join(user_folder, 'html')
        os.makedirs(html_folder, exist_ok=True)
        html_filename = filename.rsplit('.', 1)[0] + '.html'
        html_path = os.path.join(html_folder, html_filename)
        success = extract_text_and_images_from_docx(file_path, html_path, new_book.id)
    elif file_ext == 'fb2':
        html_folder = os.path.join(user_folder, 'html')
        os.makedirs(html_folder, exist_ok=True)
        html_filename = filename.rsplit('.', 1)[0] + '.html'
        html_path = os.path.join(html_folder, html_filename)
        success = extract_text_and_images_from_fb2(file_path, html_path, new_book.id)
    elif file_ext == 'txt':
        html_folder = os.path.join(user_folder, 'html')
        os.makedirs(html_folder, exist_ok=True)
        html_filename = filename.rsplit('.', 1)[0] + '.html'
        html_path = os.path.join(html_folder, html_filename)
        success = extract_text_from_txt(file_path, html_path, new_book.id)
    elif file_ext == 'rtf':
        html_folder = os.path.join(user_folder, 'html')
        os.makedirs(html_folder, exist_ok=True)
        html_filename = filename.rsplit('.', 1)[0] + '.html'
        html_path = os.path.join(html_folder, html_filename)
        success = extract_text_from_rtf(file_path, html_path, new_book.id)

    if success:
        new_book.extracted_html_path = html_path
        db.session.commit()
        print(f"HTML создан: {html_path}")
        return True, f"Книга {filename} успешно загружена и обработана."
    else:
        print(f"Не удалось извлечь текст из {filename}")
        return False, f"Ошибка при обработке {filename}. Текст не извлечён."

@app.route('/upload/<int:user_id>', methods=['GET', 'POST'])
def upload(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session['user_id'] != user_id:
        return "Доступ запрещён", 403
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        if 'files[]' not in request.files:
            flash('Нет выбранных файлов', 'error')
            return redirect(url_for('upload', user_id=user.id))
        
        files = request.files.getlist('files[]')
        # Удаляем пустые (если пользователь выбрал, но потом убрал)
        files = [f for f in files if f and f.filename]
        if not files:
            flash('Файлы не выбраны', 'error')
            return redirect(url_for('upload', user_id=user.id))
        
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        
        success_count = 0
        error_messages = []
        for file in files:
            if allowed_file(file.filename):
                success, msg = process_uploaded_file(file, user, user_folder)
                if success:
                    success_count += 1
                else:
                    error_messages.append(msg)
            else:
                error_messages.append(f'Недопустимый формат: {file.filename}')
        
        # Формируем итоговое сообщение
        if success_count > 0:
            flash(f'Успешно загружено {success_count} книг.', 'success')
        for err in error_messages:
            flash(err, 'error')
        
        return redirect(url_for('profile', user_id=user.id))
    
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
                           style_vars=style_vars,
                           last_position=book.last_position)

@app.route('/save_position/<int:book_id>', methods=['POST'])
def save_position(book_id):
    """Сохраняет позицию чтения (количество прочитанных символов)."""
    if 'user_id' not in session:
        return 'Unauthorized', 401
    book = Book.query.get_or_404(book_id)
    if book.user_id != session['user_id']:
        return 'Forbidden', 403
    data = request.get_json()
    if data and 'position' in data:
        book.last_position = int(data['position'])
        db.session.commit()
        return 'OK', 200
    return 'Bad request', 400

@app.route('/update_reader_settings', methods=['POST'])
def update_reader_settings():
    if 'user_id' not in session:
        return 'Unauthorized', 401
    user = User.query.get(session['user_id'])
    if not user:
        return 'Not found', 404
    data = request.get_json()
    if 'preferred_font' in data:
        user.preferred_font = data['preferred_font']
    if 'font_pref' in data:
        user.font_pref = data['font_pref']
    if 'line_height' in data:
        user.line_height = data['line_height']
    if 'light_sensitivity_level' in data:
        user.light_sensitivity_level = data['light_sensitivity_level']
    if 'contrast_sensitivity' in data:
        user.contrast_sensitivity = data['contrast_sensitivity']
    if 'brightness_preference' in data:
        user.brightness_preference = data['brightness_preference']
    if 'preferred_line_width_ch' in data:
        user.preferred_line_width_ch = data['preferred_line_width_ch']
    db.session.commit()
    return 'OK', 200
    
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
    # Возвращаемся на ту же страницу с сохранением номера страницы
    page = request.args.get('page', 1, type=int)
    return redirect(url_for('profile', user_id=session['user_id'], page=page))

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
    classes = []
    css_vars = {}

    # Размер шрифта
    font_size = getattr(user, 'font_pref', 'medium')
    classes.append(f'font-{font_size}')

    # Тема (с учётом дальтонизма)
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

    # Шрифт
    preferred_font = getattr(user, 'preferred_font', 'Roboto')
    font_class = f"font-{preferred_font.lower().replace(' ', '-')}"
    classes.append(font_class)

    # Межстрочный интервал
    line_height = getattr(user, 'line_height', 'normal')
    classes.append(f'line-height-{line_height}')

    # Уровень светочувствительности
    light_level = getattr(user, 'light_sensitivity_level', 'low')
    
    # Ширина строки
    line_width = getattr(user, 'preferred_line_width_ch', 66)
    css_vars['--line-width'] = f'{line_width}ch'

    # Контраст (только если не 50 или если light_level не 'low')
    contrast_val = getattr(user, 'contrast_sensitivity', 50)
    # Если светочувствительность не 'low', используем предустановки
    if light_level == 'medium':
        contrast_factor = 1.2
        darkness = 0.2
    elif light_level == 'high':
        contrast_factor = 1.5
        darkness = 0.4
    else:  # 'low' или 'manual'
        # При ручной настройке используем значения ползунков
        contrast_factor = 0.5 + (contrast_val / 100) * 1.5
        brightness_val = getattr(user, 'brightness_preference', 50)
        # Новая формула: при 50% яркости darkness = 0, при 0% darkness = 0.7
        darkness = max(0, (50 - brightness_val) / 50 * 0.7)
        darkness = min(darkness, 1)  # ограничиваем сверху
    
    css_vars['--text-contrast'] = f'{contrast_factor}'
    if darkness > 0:
        css_vars['--bg-darkness'] = f'{darkness}'

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