import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
import uuid

# Инициализация приложения
app = Flask(__name__)
app.config.from_object(Config)

# Создание папок для загрузок
os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True)
os.makedirs(app.config['THUMBNAIL_FOLDER'], exist_ok=True)

# Инициализация базы данных
db = SQLAlchemy(app)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Модели базы данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), default='default-avatar.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    videos = db.relationship('Video', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(200), default='default-thumbnail.jpg')
    views = db.Column(db.Integer, default=0)
    duration = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.relationship('Like', backref='video', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='video', lazy=True, cascade='all, delete-orphan')
    tags = db.Column(db.String(500))


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'video_id', name='unique_like'),)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Вспомогательные функции
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def generate_unique_filename(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    return unique_filename


# Маршруты
@app.route('/')
def index():
    # Получаем популярные видео (по просмотрам)
    popular_videos = Video.query.order_by(Video.views.desc()).limit(12).all()

    # Получаем новые видео
    new_videos = Video.query.order_by(Video.created_at.desc()).limit(12).all()

    # Если пользователь авторизован, получаем рекомендации
    recommended_videos = []
    if current_user.is_authenticated:
        # Простая рекомендательная система: видео от авторов, которых пользователь лайкал
        user_likes = Like.query.filter_by(user_id=current_user.id).all()
        liked_video_ids = [like.video_id for like in user_likes]

        if liked_video_ids:
            # Находим авторов лайкнутых видео
            liked_videos = Video.query.filter(Video.id.in_(liked_video_ids)).all()
            liked_authors = [video.user_id for video in liked_videos]

            # Рекомендуем другие видео этих авторов
            recommended_videos = Video.query.filter(
                Video.user_id.in_(liked_authors),
                ~Video.id.in_(liked_video_ids)
            ).order_by(db.func.random()).limit(12).all()

    # Если нет рекомендаций, показываем случайные видео
    if not recommended_videos:
        recommended_videos = Video.query.order_by(db.func.random()).limit(12).all()

    return render_template('index.html',
                           popular_videos=popular_videos,
                           new_videos=new_videos,
                           recommended_videos=recommended_videos)


@app.route('/feed')
@login_required
def feed():
    # Лента подписок (в данной версии - видео всех пользователей)
    # В будущем можно добавить систему подписок
    feed_videos = Video.query.order_by(Video.created_at.desc()).limit(20).all()
    return render_template('feed.html', videos=feed_videos)


@app.route('/video/<int:video_id>')
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)

    # Увеличиваем количество просмотров
    video.views += 1
    db.session.commit()

    # Проверяем, лайкнул ли текущий пользователь это видео
    user_liked = False
    if current_user.is_authenticated:
        like = Like.query.filter_by(user_id=current_user.id, video_id=video_id).first()
        user_liked = like is not None

    # Получаем комментарии
    comments = Comment.query.filter_by(video_id=video_id).order_by(Comment.created_at.desc()).all()

    # Получаем похожие видео (по тегам)
    similar_videos = []
    if video.tags:
        tags = video.tags.split(',')
        for tag in tags[:3]:
            tagged_videos = Video.query.filter(
                Video.tags.contains(tag.strip()),
                Video.id != video_id
            ).limit(4).all()
            similar_videos.extend(tagged_videos)

    # Убираем дубликаты
    similar_videos = list({v.id: v for v in similar_videos}.values())[:6]

    return render_template('video.html',
                           video=video,
                           user_liked=user_liked,
                           comments=comments,
                           similar_videos=similar_videos)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        # Проверяем, есть ли файл в запросе
        if 'video' not in request.files:
            flash('No video file selected', 'error')
            return redirect(request.url)

        file = request.files['video']

        if file.filename == '':
            flash('No video selected', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            # Генерируем уникальное имя файла
            filename = generate_unique_filename(file.filename)

            # Сохраняем видео
            video_path = os.path.join(app.config['VIDEO_FOLDER'], filename)
            file.save(video_path)

            # Создаем запись в базе данных
            video = Video(
                user_id=current_user.id,
                title=request.form.get('title', 'Untitled'),
                description=request.form.get('description', ''),
                filename=filename,
                tags=request.form.get('tags', ''),
                duration='0:00'  # В реальном приложении здесь нужно определить длительность
            )

            # Сохраняем thumbnail если есть
            if 'thumbnail' in request.files:
                thumbnail_file = request.files['thumbnail']
                if thumbnail_file.filename != '':
                    thumbnail_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower()
                    thumbnail_filename = f"{uuid.uuid4().hex}.{thumbnail_ext}"
                    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                    thumbnail_file.save(thumbnail_path)
                    video.thumbnail = thumbnail_filename

            db.session.add(video)
            db.session.commit()

            flash('Video uploaded successfully!', 'success')
            return redirect(url_for('video_detail', video_id=video.id))
        else:
            flash('Invalid file type. Allowed types: mp4, avi, mov, mkv, webm', 'error')

    return render_template('upload.html')


@app.route('/like/<int:video_id>', methods=['POST'])
@login_required
def like_video(video_id):
    video = Video.query.get_or_404(video_id)

    # Проверяем, не лайкнул ли уже пользователь это видео
    existing_like = Like.query.filter_by(user_id=current_user.id, video_id=video_id).first()

    if existing_like:
        # Удаляем лайк
        db.session.delete(existing_like)
        liked = False
    else:
        # Добавляем лайк
        like = Like(user_id=current_user.id, video_id=video_id)
        db.session.add(like)
        liked = True

    db.session.commit()

    # Получаем обновленное количество лайков
    like_count = Like.query.filter_by(video_id=video_id).count()

    return jsonify({
        'liked': liked,
        'like_count': like_count
    })


@app.route('/comment/<int:video_id>', methods=['POST'])
@login_required
def add_comment(video_id):
    content = request.form.get('content', '').strip()

    if not content:
        return jsonify({'error': 'Comment cannot be empty'}), 400

    video = Video.query.get_or_404(video_id)

    comment = Comment(
        user_id=current_user.id,
        video_id=video_id,
        content=content
    )

    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'success': True,
        'comment': {
            'id': comment.id,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'author': {
                'id': current_user.id,
                'username': current_user.username,
                'avatar': url_for('static', filename=f'uploads/thumbnails/{current_user.avatar}')
            }
        }
    })


@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    videos = Video.query.filter_by(user_id=user.id).order_by(Video.created_at.desc()).all()

    # Статистика пользователя
    total_views = sum(video.views for video in videos)
    total_likes = sum(Like.query.filter_by(video_id=video.id).count() for video in videos)

    return render_template('profile.html',
                           user=user,
                           videos=videos,
                           total_views=total_views,
                           total_likes=total_likes)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Logged in successfully!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Валидация
        errors = []

        if User.query.filter_by(username=username).first():
            errors.append('Username already exists')

        if User.query.filter_by(email=email).first():
            errors.append('Email already registered')

        if password != confirm_password:
            errors.append('Passwords do not match')

        if len(password) < 6:
            errors.append('Password must be at least 6 characters')

        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            # Создаем нового пользователя
            user = User(username=username, email=email)
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


@app.route('/search')
def search():
    query = request.args.get('q', '')

    if query:
        # Ищем видео по названию, описанию и тегам
        videos = Video.query.filter(
            db.or_(
                Video.title.ilike(f'%{query}%'),
                Video.description.ilike(f'%{query}%'),
                Video.tags.ilike(f'%{query}%')
            )
        ).order_by(Video.created_at.desc()).all()
    else:
        videos = []

    return render_template('search.html', videos=videos, query=query)


# Статические файлы
@app.route('/uploads/videos/<filename>')
def uploaded_video(filename):
    return send_from_directory(app.config['VIDEO_FOLDER'], filename)


@app.route('/uploads/thumbnails/<filename>')
def uploaded_thumbnail(filename):
    return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename)


# Обработчик ошибок 404
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


# Инициализация базы данных
@app.before_request
def create_tables():
    db.create_all()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
