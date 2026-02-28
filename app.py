import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from epub_parser import extract_text_from_epub, get_epub_title
from pdf_parser import extract_text_from_pdf, get_pdf_title
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session

# ================== КОНФИГУРАЦИЯ ==================
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Настройки загрузки файлов
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'epub', 'pdf', 'fb2'}
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
    """Страница теста зрения. Если пользователь залогинен — обновляет его настройки, иначе предлагает войти."""
    # Проверяем, залогинен ли пользователь
    if 'user_id' not in session:
        # Если не залогинен, перенаправляем на страницу входа с сообщением
        return redirect(url_for('login', next=url_for('test')))
    
    # Получаем текущего пользователя из сессии
    user = User.query.get(session['user_id'])
    if not user:
        # Если пользователь не найден (маловероятно), очищаем сессию и просим войти заново
        session.pop('user_id', None)
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Получаем данные из формы
        vision = request.form.get('vision', 'medium')
        contrast = request.form.get('contrast', 'normal')
        color = request.form.get('color', 'normal')
        
        # Обновляем поля существующего пользователя
        user.font_pref = vision
        user.theme_pref = contrast
        user.color_vision = color
        user.contrast = contrast  # если нужно отдельное поле для контраста
        
        db.session.commit()
        
        # Перенаправляем в профиль
        return redirect(url_for('profile', user_id=user.id))
    
    # GET-запрос — показываем форму теста
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

                success = extract_text_from_epub(file_path, html_path)
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

                success = extract_text_from_pdf(file_path, html_path)
                if success:
                    new_book.extracted_html_path = html_path
                    db.session.commit()
                    print(f"HTML создан: {html_path}")
                else:
                    print(f"Не удалось извлечь текст из PDF: {filename}")

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

    # Формируем классы для body на основе настроек пользователя
    
    body_classes = []

    # Размер шрифта
    font_pref = user.font_pref if user and user.font_pref else 'medium'
    body_classes.append(f'font-{font_pref}')

    # Тема
    theme_pref = user.theme_pref if user and user.theme_pref else 'normal'
    body_classes.append(f'theme-{theme_pref}')

    # Гарнитура (по умолчанию sans-serif, если serif не выбран)
    # Пока нет отдельного поля, можно ориентироваться на что-то, но мы добавим позже.
    # Пока просто добавим класс sans-serif или serif, если будет поле.
    # Для демо добавим проверку: если пользователь выбрал "serif" (можно потом добавить в тест)
    # Но сейчас нет такого поля. Поэтому пока без класса serif.
    # Можно захардкодить serif для определённого пользователя или оставить пустым.

    # Собираем строку классов
    body_class_str = ' '.join(body_classes)
    

    return render_template('reader.html',
                           book=book,
                           book_content=book_content,
                           user_id=book.user_id,
                           body_classes=body_class_str)
    

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

# ================== ЗАПУСК ==================
if __name__ == '__main__':
    app.run(debug=True)