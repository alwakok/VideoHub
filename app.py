import os
import random
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

# Константы для проверки файлов
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

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
    avatar = db.Column(db.String(200), default='default_avatar.png')
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    theme = db.Column(db.String(20), default='light')  # Добавляем поле для темы
    terms_accepted_at = db.Column(db.DateTime, nullable=True)
    videos = db.relationship('Video', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    playlists = db.relationship('Playlist', backref='user', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade='all, delete-orphan')
    watch_history = db.relationship('WatchHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', foreign_keys='Subscription.subscriber_id', backref='subscriber',
                                    lazy=True)
    subscribers = db.relationship('Subscription', foreign_keys='Subscription.channel_id', backref='channel', lazy=True)

    def set_password(self, password):
        """Устанавливает хеш пароля"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Проверяет пароль"""
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


class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    videos = db.relationship('PlaylistVideo', backref='playlist', lazy=True, cascade='all, delete-orphan')
    thumbnail = db.Column(db.String(200), default='default-playlist.png')


class PlaylistVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('playlist_id', 'video_id', name='unique_playlist_video'),)


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'video_id', name='unique_favorite'),)


class WatchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'video_id', name='unique_watch_history'),)
    video = db.relationship('Video', backref='watch_histories', lazy=True)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('subscriber_id', 'channel_id', name='unique_subscription'),)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Вспомогательные функции
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def generate_unique_filename(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    return unique_filename


def get_video_duration(file_path):
    """Определяет длительность видео файла"""
    try:
        # Сначала пробуем использовать MoviePy если установлен
        try:
            from moviepy.editor import VideoFileClip
            with VideoFileClip(file_path) as video:
                duration = video.duration
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                return f"{minutes}:{seconds:02d}"
        except ImportError:
            pass

        # Пробуем использовать OpenCV если установлен
        try:
            import cv2
            video = cv2.VideoCapture(file_path)
            fps = video.get(cv2.CAP_PROP_FPS)
            frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
            video.release()

            if fps > 0 and frame_count > 0:
                duration_seconds = frame_count / fps
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                return f"{minutes}:{seconds:02d}"
        except ImportError:
            pass

        # Простой способ для MP4 файлов
        try:
            import struct
            with open(file_path, 'rb') as f:
                # Читаем начало файла для определения формата
                data = f.read(100)

                # Для MP4 файлов ищем атомы
                if b'ftyp' in data or b'moov' in data:
                    # Пытаемся определить длительность по размеру файла
                    file_size = os.path.getsize(file_path)

                    # Грубая оценка: 1 минута ≈ 10MB для 720p
                    estimated_minutes = file_size / (10 * 1024 * 1024)
                    if estimated_minutes < 1:
                        estimated_minutes = 1
                    elif estimated_minutes > 60:
                        estimated_minutes = 60

                    minutes = int(estimated_minutes)
                    seconds = int((estimated_minutes - minutes) * 60)
                    return f"{minutes}:{seconds:02d}"

        except:
            pass

        # Если ничего не сработало, используем случайную длительность
        # Но на основе размера файла для большей точности
        try:
            file_size = os.path.getsize(file_path)
            # Примерная оценка: 1MB ≈ 10 секунд для среднего качества
            estimated_seconds = file_size / (100 * 1024)  # 100KB в секунду
            if estimated_seconds < 30:
                estimated_seconds = 30
            elif estimated_seconds > 1800:  # 30 минут максимум
                estimated_seconds = 1800

            minutes = int(estimated_seconds // 60)
            seconds = int(estimated_seconds % 60)
            return f"{minutes}:{seconds:02d}"

        except:
            # Последний резерв - случайная длительность
            minutes = random.randint(1, 30)
            seconds = random.randint(0, 59)
            return f"{minutes}:{seconds:02d}"

    except Exception as e:
        print(f"Ошибка при определении длительности видео: {e}")
        # Резервный вариант
        minutes = random.randint(1, 30)
        seconds = random.randint(0, 59)
        return f"{minutes}:{seconds:02d}"


def extract_video_thumbnail(video_path, thumbnail_path):
    """Извлекает первый кадр из видео для обложки"""
    try:
        # Пробуем использовать OpenCV
        try:
            import cv2
            video = cv2.VideoCapture(video_path)
            success, frame = video.read()
            video.release()

            if success:
                cv2.imwrite(thumbnail_path, frame)
                return True
        except ImportError:
            pass

        # Пробуем использовать MoviePy
        try:
            from moviepy.editor import VideoFileClip
            with VideoFileClip(video_path) as video:
                # Сохраняем первый кадр
                video.save_frame(thumbnail_path, t=0)
                return True
        except ImportError:
            pass

        # Если библиотеки не установлены, копируем дефолтную обложку
        default_thumbnail = os.path.join(app.config['THUMBNAIL_FOLDER'], 'default-thumbnail.jpg')
        if os.path.exists(default_thumbnail):
            import shutil
            shutil.copy(default_thumbnail, thumbnail_path)
            return True

        return False
    except Exception as e:
        print(f"Ошибка при создании обложки: {e}")
        return False


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

            # Получаем длительность видео
            duration = get_video_duration(video_path)

            # Создаем запись в базе данных
            video = Video(
                user_id=current_user.id,
                title=request.form.get('title', 'Untitled'),
                description=request.form.get('description', ''),
                filename=filename,
                tags=request.form.get('tags', ''),
                duration=duration
            )

            # Сохраняем thumbnail если есть
            thumbnail_filename = None
            if 'thumbnail' in request.files:
                thumbnail_file = request.files['thumbnail']
                if thumbnail_file and thumbnail_file.filename != '':
                    if allowed_image_file(thumbnail_file.filename):
                        thumbnail_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower()
                        thumbnail_filename = f"{uuid.uuid4().hex}.{thumbnail_ext}"
                        thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                        thumbnail_file.save(thumbnail_path)
                        video.thumbnail = thumbnail_filename

            # Если thumbnail не загружен, создаем из первого кадра видео
            if not thumbnail_filename:
                thumbnail_filename = f"thumbnail_{uuid.uuid4().hex}.jpg"
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                if extract_video_thumbnail(video_path, thumbnail_path):
                    video.thumbnail = thumbnail_filename
                else:
                    # Если не удалось извлечь кадр, используем дефолтную обложку
                    video.thumbnail = 'default-thumbnail.jpg'

            db.session.add(video)
            db.session.commit()

            flash('Video uploaded successfully!', 'success')
            return redirect(url_for('video_detail', video_id=video.id))
        else:
            flash('Invalid file type. Allowed types: mp4, avi, mov, mkv, webm', 'error')

    return render_template('upload.html')

@app.route('/terms')
def terms():
    """Страница с пользовательским соглашением"""
    return render_template('terms.html')

@app.route('/watch-together')
def watch_together():
    """Страница совместного просмотра (заглушка)"""
    return render_template('watch_together.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        accept_terms = request.form.get('accept_terms')  # чекбокс согласия

        errors = []

        # Проверка согласия с условиями
        if accept_terms != 'on':
            errors.append('Вы должны принять пользовательское соглашение')

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
            user = User(
                username=username,
                email=email,
                avatar='default_avatar.png',
                terms_accepted_at=datetime.utcnow()  # записываем дату согласия
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/video/edit/<int:video_id>', methods=['GET', 'POST'])
@login_required
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)

    # Проверяем, что пользователь - владелец видео
    if current_user.id != video.user_id:
        flash('Вы не можете редактировать это видео', 'error')
        return redirect(url_for('video_detail', video_id=video_id))

    if request.method == 'POST':
        # Обновляем заголовок
        title = request.form.get('title', '').strip()
        if title:
            video.title = title

        # Обновляем описание
        description = request.form.get('description', '').strip()
        video.description = description if description else None

        # Обновляем теги
        tags = request.form.get('tags', '').strip()
        video.tags = tags if tags else None

        # Обработка новой обложки
        if 'thumbnail' in request.files:
            thumbnail_file = request.files['thumbnail']
            if thumbnail_file and thumbnail_file.filename != '':
                if allowed_image_file(thumbnail_file.filename):
                    # Удаляем старую обложку если она не дефолтная
                    if video.thumbnail and video.thumbnail != 'default-thumbnail.jpg':
                        old_thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
                        if os.path.exists(old_thumbnail_path):
                            try:
                                os.remove(old_thumbnail_path)
                            except:
                                pass

                    # Сохраняем новую обложку
                    thumbnail_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower()
                    thumbnail_filename = f"thumbnail_{video_id}_{uuid.uuid4().hex[:8]}.{thumbnail_ext}"
                    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                    thumbnail_file.save(thumbnail_path)
                    video.thumbnail = thumbnail_filename

        # Удаление текущей обложки (установка дефолтной)
        if request.form.get('remove_thumbnail') == 'true':
            if video.thumbnail and video.thumbnail != 'default-thumbnail.jpg':
                old_thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
                if os.path.exists(old_thumbnail_path):
                    try:
                        os.remove(old_thumbnail_path)
                    except:
                        pass
            video.thumbnail = 'default-thumbnail.jpg'

        db.session.commit()
        flash('Видео успешно обновлено!', 'success')
        return redirect(url_for('video_detail', video_id=video_id))

    return render_template('edit_video.html', video=video)


# Также добавьте этот маршрут для обработки AJAX-запросов на получение информации о видео
@app.route('/api/video/<int:video_id>')
@login_required
def get_video_info(video_id):
    video = Video.query.get_or_404(video_id)

    # Проверяем, что пользователь - владелец видео
    if current_user.id != video.user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify({
        'id': video.id,
        'title': video.title,
        'description': video.description or '',
        'tags': video.tags or '',
        'thumbnail': url_for('uploaded_thumbnail', filename=video.thumbnail)
    })


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

    # Получаем URL для аватара пользователя
    avatar_url = url_for('uploaded_thumbnail', filename=current_user.avatar)

    # Форматируем дату в единый формат
    formatted_date = comment.created_at.strftime('%d.%m.%Y %H:%M')

    return jsonify({
        'success': True,
        'comment': {
            'id': comment.id,
            'content': comment.content,
            'created_at': formatted_date,  # Используем отформатированную дату
            'author': {
                'id': current_user.id,
                'username': current_user.username,
                'avatar': avatar_url
            }
        }
    })


@app.route('/video/delete/<int:video_id>', methods=['POST'])
@login_required
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)

    # Проверяем, что пользователь - владелец видео
    if current_user.id != video.user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Удаляем файл видео
        video_path = os.path.join(app.config['VIDEO_FOLDER'], video.filename)
        if os.path.exists(video_path):
            os.remove(video_path)

        # Удаляем thumbnail если он не дефолтный
        if video.thumbnail and video.thumbnail != 'default-thumbnail.jpg':
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)

        # Удаляем запись из базы данных
        db.session.delete(video)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Video deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        # Обработка загрузки аватарки
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file and avatar_file.filename != '':
                if allowed_image_file(avatar_file.filename):
                    # Генерируем уникальное имя файла
                    ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                    avatar_filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                    avatar_path = os.path.join(app.config['THUMBNAIL_FOLDER'], avatar_filename)

                    # Сохраняем файл
                    avatar_file.save(avatar_path)

                    # Удаляем старый аватар если он существует и не дефолтный
                    if current_user.avatar and current_user.avatar != 'default_avatar.png':
                        old_avatar_path = os.path.join(app.config['THUMBNAIL_FOLDER'], current_user.avatar)
                        if os.path.exists(old_avatar_path):
                            try:
                                os.remove(old_avatar_path)
                            except:
                                pass

                    # Обновляем в БД
                    current_user.avatar = avatar_filename
                    db.session.commit()
                    flash('Аватар успешно обновлен!', 'success')
                else:
                    flash('Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF', 'error')

        # Удаление аватарки
        if request.form.get('remove_avatar') == 'true':
            if current_user.avatar and current_user.avatar != 'default_avatar.png':
                old_avatar_path = os.path.join(app.config['THUMBNAIL_FOLDER'], current_user.avatar)
                if os.path.exists(old_avatar_path):
                    try:
                        os.remove(old_avatar_path)
                    except:
                        pass
            # Устанавливаем дефолтный аватар
            current_user.avatar = 'default_avatar.png'
            db.session.commit()
            flash('Аватар удален, установлен аватар по умолчанию', 'success')

        # Обновление имени пользователя
        new_username = request.form.get('username', '').strip()
        if new_username and new_username != current_user.username:
            if User.query.filter_by(username=new_username).first():
                flash('Это имя пользователя уже занято', 'error')
            else:
                current_user.username = new_username
                db.session.commit()
                flash('Имя пользователя успешно обновлено!', 'success')

        # Обновление email
        new_email = request.form.get('email', '').strip()
        if new_email and new_email != current_user.email:
            if User.query.filter_by(email=new_email).first():
                flash('Этот email уже зарегистрирован', 'error')
            else:
                current_user.email = new_email
                db.session.commit()
                flash('Email успешно обновлен!', 'success')

        # Обновление описания профиля
        bio = request.form.get('bio', '').strip()
        current_user.bio = bio if bio else None
        db.session.commit()

        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('profile', username=current_user.username))

    return render_template('edit_profile.html')


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



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()

    if query:
        # Безопасный поиск с использованием параметров
        search_pattern = f'%{query}%'
        videos = Video.query.filter(
            db.or_(
                Video.title.ilike(search_pattern),
                Video.description.ilike(search_pattern),
                Video.tags.ilike(search_pattern)
            )
        ).order_by(Video.created_at.desc()).all()
    else:
        videos = []

    return render_template('search.html', videos=videos, query=query)


# Новые маршруты для плейлистов, избранного и истории

@app.route('/api/theme', methods=['POST'])
@login_required
def update_theme():
    data = request.get_json()
    theme = data.get('theme', 'light')

    if theme not in ['light', 'dark']:
        return jsonify({'error': 'Invalid theme'}), 400

    current_user.theme = theme
    db.session.commit()

    return jsonify({'success': True, 'theme': theme})


@app.route('/favorites')
@login_required
def favorites():
    favorites = Favorite.query.filter_by(user_id=current_user.id) \
        .order_by(Favorite.created_at.desc()).all()
    favorite_videos = [fav.video for fav in favorites]

    return render_template('favorites.html', videos=favorite_videos)


@app.route('/favorite/<int:video_id>', methods=['POST'])
@login_required
def toggle_favorite(video_id):
    video = Video.query.get_or_404(video_id)

    existing_fav = Favorite.query.filter_by(
        user_id=current_user.id,
        video_id=video_id
    ).first()

    if existing_fav:
        db.session.delete(existing_fav)
        favorited = False
    else:
        favorite = Favorite(user_id=current_user.id, video_id=video_id)
        db.session.add(favorite)
        favorited = True

    db.session.commit()

    return jsonify({
        'favorited': favorited,
        'favorite_count': Favorite.query.filter_by(video_id=video_id).count()
    })


@app.route('/playlists')
@login_required
def playlists():
    return render_template('playlists.html', playlists=current_user.playlists)


@app.route('/playlist/create', methods=['POST'])
@login_required
def create_playlist():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    is_public = request.form.get('is_public', 'true') == 'true'

    if not name:
        return jsonify({'error': 'Название обязательно'}), 400

    playlist = Playlist(
        user_id=current_user.id,
        name=name,
        description=description,
        is_public=is_public
    )

    db.session.add(playlist)
    db.session.commit()

    return jsonify({
        'success': True,
        'playlist': {
            'id': playlist.id,
            'name': playlist.name,
            'description': playlist.description
        }
    })


@app.route('/playlist/<int:playlist_id>')
@login_required
def playlist_detail(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    if playlist.user_id != current_user.id and not playlist.is_public:
        flash('Этот плейлист приватный', 'error')
        return redirect(url_for('playlists'))

    return render_template('playlist_detail.html', playlist=playlist)


@app.route('/playlist/<int:playlist_id>/add/<int:video_id>', methods=['POST'])
@login_required
def add_to_playlist(playlist_id, video_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    if playlist.user_id != current_user.id:
        return jsonify({'error': 'Недостаточно прав'}), 403

    video = Video.query.get_or_404(video_id)

    # Проверяем, не добавлено ли уже
    existing = PlaylistVideo.query.filter_by(
        playlist_id=playlist_id,
        video_id=video_id
    ).first()

    if existing:
        return jsonify({'error': 'Видео уже в плейлисте'}), 400

    playlist_video = PlaylistVideo(playlist_id=playlist_id, video_id=video_id)
    db.session.add(playlist_video)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/watch_history')
@login_required
def watch_history():
    history = WatchHistory.query.filter_by(user_id=current_user.id) \
        .order_by(WatchHistory.watched_at.desc()).limit(50).all()
    watched_videos = [h.video for h in history]

    return render_template('history.html', videos=watched_videos)


@app.route('/api/add_to_history/<int:video_id>', methods=['POST'])
@login_required
def add_to_history(video_id):
    video = Video.query.get_or_404(video_id)

    # Проверяем, есть ли уже в истории
    existing = WatchHistory.query.filter_by(
        user_id=current_user.id,
        video_id=video_id
    ).first()

    if existing:
        existing.watched_at = datetime.utcnow()
    else:
        history = WatchHistory(user_id=current_user.id, video_id=video_id)
        db.session.add(history)

    db.session.commit()

    return jsonify({'success': True})


@app.route('/subscriptions')
@login_required
def subscriptions():
    # Получаем каналы, на которые подписан пользователь
    subscriptions = Subscription.query.filter_by(subscriber_id=current_user.id).all()
    subscribed_channels = [User.query.get(sub.channel_id) for sub in subscriptions]

    return render_template('subscriptions.html', channels=subscribed_channels)


# Статические файлы
@app.route('/uploads/videos/<filename>')
def uploaded_video(filename):
    return send_from_directory(app.config['VIDEO_FOLDER'], filename)


@app.route('/uploads/thumbnails/<filename>')
def uploaded_thumbnail(filename):
    if not filename:
        filename = 'default_avatar.png'
    return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename)


# Обработчик ошибок 404
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


# Инициализация базы данных
@app.before_request
def create_tables():
    """Создание таблиц при необходимости перед каждым запросом"""
    if not hasattr(app, 'tables_created'):
        db.create_all()
        app.tables_created = True


# Создание стандартных плейлистов для пользователей
def init_database():
    """Инициализация базы данных при первом запуске"""
    with app.app_context():
        try:
            db.create_all()
            print("Таблицы базы данных созданы")

            # Создаем стандартные плейлисты для всех пользователей
            users = User.query.all()
            for user in users:
                # Проверяем, есть ли у пользователя плейлист "Избранное"
                existing = Playlist.query.filter_by(
                    user_id=user.id,
                    name="Избранное"
                ).first()

                if not existing:
                    playlist = Playlist(
                        user_id=user.id,
                        name="Избранное",
                        description="Мои любимые видео",
                        is_public=False
                    )
                    db.session.add(playlist)

            db.session.commit()
            print("Стандартные плейлисты созданы")

        except Exception as e:
            print(f"Ошибка при инициализации БД: {e}")


# Инициализируем базу данных при запуске
init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)