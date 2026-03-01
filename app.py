import os
import random
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
import uuid

app = Flask(__name__)
app.config.from_object(Config)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True)
os.makedirs(app.config['THUMBNAIL_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

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
    theme = db.Column(db.String(20), default='light')
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


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def generate_unique_filename(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return f"{uuid.uuid4().hex}.{ext}"


def get_video_duration(file_path):
    try:
        try:
            from moviepy.editor import VideoFileClip
            with VideoFileClip(file_path) as video:
                duration = video.duration
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                return f"{minutes}:{seconds:02d}"
        except ImportError:
            pass

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

        file_size = os.path.getsize(file_path)
        estimated_seconds = file_size / (100 * 1024)
        estimated_seconds = max(30, min(estimated_seconds, 1800))

        minutes = int(estimated_seconds // 60)
        seconds = int(estimated_seconds % 60)
        return f"{minutes}:{seconds:02d}"

    except Exception as e:
        print(f"Ошибка при определении длительности видео: {e}")
        return f"{random.randint(1, 30)}:{random.randint(0, 59):02d}"


def extract_video_thumbnail(video_path, thumbnail_path):
    try:
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

        try:
            from moviepy.editor import VideoFileClip
            with VideoFileClip(video_path) as video:
                video.save_frame(thumbnail_path, t=0)
                return True
        except ImportError:
            pass

        default_thumbnail = os.path.join(app.config['THUMBNAIL_FOLDER'], 'default-thumbnail.jpg')
        if os.path.exists(default_thumbnail):
            import shutil
            shutil.copy(default_thumbnail, thumbnail_path)
            return True

        return False
    except Exception as e:
        print(f"Ошибка при создании обложки: {e}")
        return False


def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def create_default_playlists(user_id):
    existing = Playlist.query.filter_by(user_id=user_id, name="Избранное").first()
    if not existing:
        playlist = Playlist(
            user_id=user_id,
            name="Избранное",
            description="Мои любимые видео",
            is_public=False
        )
        db.session.add(playlist)
        db.session.commit()


@app.route('/')
def index():
    popular_videos = Video.query.order_by(Video.views.desc()).limit(12).all()
    new_videos = Video.query.order_by(Video.created_at.desc()).limit(12).all()

    recommended_videos = []
    if current_user.is_authenticated:
        liked_video_ids = [like.video_id for like in current_user.likes]

        if liked_video_ids:
            liked_authors = db.session.query(Video.user_id).filter(Video.id.in_(liked_video_ids)).distinct().all()
            liked_authors = [author[0] for author in liked_authors]

            recommended_videos = Video.query.filter(
                Video.user_id.in_(liked_authors),
                ~Video.id.in_(liked_video_ids)
            ).order_by(db.func.random()).limit(12).all()

    if not recommended_videos:
        recommended_videos = Video.query.order_by(db.func.random()).limit(12).all()

    return render_template('index.html',
                           popular_videos=popular_videos,
                           new_videos=new_videos,
                           recommended_videos=recommended_videos)


@app.route('/video/<int:video_id>')
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)
    video.views += 1
    db.session.commit()

    user_liked = current_user.is_authenticated and Like.query.filter_by(
        user_id=current_user.id, video_id=video_id).first() is not None

    comments = Comment.query.filter_by(video_id=video_id).order_by(Comment.created_at.desc()).all()

    similar_videos = []
    if video.tags:
        tags = [tag.strip() for tag in video.tags.split(',')[:3]]
        for tag in tags:
            tagged = Video.query.filter(
                Video.tags.contains(tag),
                Video.id != video_id
            ).limit(4).all()
            similar_videos.extend(tagged)

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
        if 'video' not in request.files:
            flash('No video file selected', 'error')
            return redirect(request.url)

        file = request.files['video']

        if file.filename == '':
            flash('No video selected', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = generate_unique_filename(file.filename)
            video_path = os.path.join(app.config['VIDEO_FOLDER'], filename)
            file.save(video_path)

            duration = get_video_duration(video_path)

            video = Video(
                user_id=current_user.id,
                title=request.form.get('title', 'Untitled'),
                description=request.form.get('description', ''),
                filename=filename,
                tags=request.form.get('tags', ''),
                duration=duration
            )

            thumbnail_filename = None
            if 'thumbnail' in request.files:
                thumbnail_file = request.files['thumbnail']
                if thumbnail_file and thumbnail_file.filename != '' and allowed_image_file(thumbnail_file.filename):
                    thumbnail_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower()
                    thumbnail_filename = f"{uuid.uuid4().hex}.{thumbnail_ext}"
                    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                    thumbnail_file.save(thumbnail_path)
                    video.thumbnail = thumbnail_filename

            if not thumbnail_filename:
                thumbnail_filename = f"thumbnail_{uuid.uuid4().hex}.jpg"
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                if extract_video_thumbnail(video_path, thumbnail_path):
                    video.thumbnail = thumbnail_filename
                else:
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
    return render_template('terms.html')


@app.route('/watch-together')
def watch_together():
    return render_template('watch_together.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        accept_terms = request.form.get('accept_terms')

        errors = []

        if accept_terms != 'on':
            errors.append('Вы должны принять пользовательское соглашение')

        if not username or len(username) < 3:
            errors.append('Имя пользователя должно содержать минимум 3 символа')
        elif User.query.filter_by(username=username).first():
            errors.append('Username already exists')

        if not email or not validate_email(email):
            errors.append('Некорректный email адрес')
        elif User.query.filter_by(email=email).first():
            errors.append('Email already registered')

        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        elif password != confirm_password:
            errors.append('Passwords do not match')

        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            user = User(
                username=username,
                email=email,
                avatar='default_avatar.png',
                terms_accepted_at=datetime.utcnow()
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()
            create_default_playlists(user.id)

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/video/edit/<int:video_id>', methods=['GET', 'POST'])
@login_required
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)

    if current_user.id != video.user_id:
        flash('Вы не можете редактировать это видео', 'error')
        return redirect(url_for('video_detail', video_id=video_id))

    if request.method == 'POST':
        video.title = request.form.get('title', '').strip() or video.title
        video.description = request.form.get('description', '').strip() or None
        video.tags = request.form.get('tags', '').strip() or None

        if 'thumbnail' in request.files:
            thumbnail_file = request.files['thumbnail']
            if thumbnail_file and thumbnail_file.filename != '' and allowed_image_file(thumbnail_file.filename):
                if video.thumbnail and video.thumbnail != 'default-thumbnail.jpg':
                    old_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except:
                            pass

                thumbnail_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower()
                thumbnail_filename = f"thumbnail_{video_id}_{uuid.uuid4().hex[:8]}.{thumbnail_ext}"
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                thumbnail_file.save(thumbnail_path)
                video.thumbnail = thumbnail_filename

        if request.form.get('remove_thumbnail') == 'true':
            if video.thumbnail and video.thumbnail != 'default-thumbnail.jpg':
                old_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except:
                        pass
            video.thumbnail = 'default-thumbnail.jpg'

        db.session.commit()
        flash('Видео успешно обновлено!', 'success')
        return redirect(url_for('video_detail', video_id=video_id))

    return render_template('edit_video.html', video=video)


@app.route('/api/video/<int:video_id>')
@login_required
def get_video_info(video_id):
    video = Video.query.get_or_404(video_id)

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
    existing_like = Like.query.filter_by(user_id=current_user.id, video_id=video_id).first()

    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        db.session.add(Like(user_id=current_user.id, video_id=video_id))
        liked = True

    db.session.commit()

    return jsonify({
        'liked': liked,
        'like_count': Like.query.filter_by(video_id=video_id).count()
    })


@app.route('/comment/<int:video_id>', methods=['POST'])
@login_required
def add_comment(video_id):
    content = request.form.get('content', '').strip()

    if not content:
        return jsonify({'error': 'Comment cannot be empty'}), 400

    Video.query.get_or_404(video_id)

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
            'created_at': comment.created_at.strftime('%d.%m.%Y %H:%M'),
            'author': {
                'id': current_user.id,
                'username': current_user.username,
                'avatar': url_for('uploaded_thumbnail', filename=current_user.avatar)
            }
        }
    })


@app.route('/video/delete/<int:video_id>', methods=['POST'])
@login_required
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)

    if current_user.id != video.user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        video_path = os.path.join(app.config['VIDEO_FOLDER'], video.filename)
        if os.path.exists(video_path):
            os.remove(video_path)

        if video.thumbnail and video.thumbnail != 'default-thumbnail.jpg':
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)

        db.session.delete(video)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    videos = Video.query.filter_by(user_id=user.id).order_by(Video.created_at.desc()).all()

    total_views = sum(video.views for video in videos)
    total_likes = sum(len(video.likes) for video in videos)

    return render_template('profile.html',
                           user=user,
                           videos=videos,
                           total_views=total_views,
                           total_likes=total_likes)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file and avatar_file.filename != '' and allowed_image_file(avatar_file.filename):
                ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                avatar_filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                avatar_path = os.path.join(app.config['THUMBNAIL_FOLDER'], avatar_filename)

                avatar_file.save(avatar_path)

                if current_user.avatar and current_user.avatar != 'default_avatar.png':
                    old_path = os.path.join(app.config['THUMBNAIL_FOLDER'], current_user.avatar)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except:
                            pass

                current_user.avatar = avatar_filename
                db.session.commit()
                flash('Аватар успешно обновлен!', 'success')
            elif avatar_file and avatar_file.filename != '':
                flash('Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF', 'error')

        if request.form.get('remove_avatar') == 'true':
            if current_user.avatar and current_user.avatar != 'default_avatar.png':
                old_path = os.path.join(app.config['THUMBNAIL_FOLDER'], current_user.avatar)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except:
                        pass
            current_user.avatar = 'default_avatar.png'
            db.session.commit()
            flash('Аватар удален, установлен аватар по умолчанию', 'success')

        new_username = request.form.get('username', '').strip()
        if new_username and new_username != current_user.username:
            if User.query.filter_by(username=new_username).first():
                flash('Это имя пользователя уже занято', 'error')
            else:
                current_user.username = new_username
                db.session.commit()
                flash('Имя пользователя успешно обновлено!', 'success')

        new_email = request.form.get('email', '').strip()
        if new_email and new_email != current_user.email:
            if not validate_email(new_email):
                flash('Некорректный email адрес', 'error')
            elif User.query.filter_by(email=new_email).first():
                flash('Этот email уже зарегистрирован', 'error')
            else:
                current_user.email = new_email
                db.session.commit()
                flash('Email успешно обновлен!', 'success')

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
    favorites = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).all()
    return render_template('favorites.html', videos=[fav.video for fav in favorites])


@app.route('/favorite/<int:video_id>', methods=['POST'])
@login_required
def toggle_favorite(video_id):
    Video.query.get_or_404(video_id)
    existing = Favorite.query.filter_by(user_id=current_user.id, video_id=video_id).first()

    if existing:
        db.session.delete(existing)
        favorited = False
    else:
        db.session.add(Favorite(user_id=current_user.id, video_id=video_id))
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

    if not name:
        return jsonify({'error': 'Название обязательно'}), 400

    playlist = Playlist(
        user_id=current_user.id,
        name=name,
        description=request.form.get('description', '').strip(),
        is_public=request.form.get('is_public', 'true') == 'true'
    )

    db.session.add(playlist)
    db.session.commit()

    return jsonify({
        'success': True,
        'playlist': {'id': playlist.id, 'name': playlist.name}
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

    if PlaylistVideo.query.filter_by(playlist_id=playlist_id, video_id=video_id).first():
        return jsonify({'error': 'Видео уже в плейлисте'}), 400

    db.session.add(PlaylistVideo(playlist_id=playlist_id, video_id=video_id))
    db.session.commit()

    return jsonify({'success': True})


@app.route('/watch_history')
@login_required
def watch_history():
    history = WatchHistory.query.filter_by(user_id=current_user.id).order_by(WatchHistory.watched_at.desc()).limit(
        50).all()
    return render_template('history.html', videos=[h.video for h in history])


@app.route('/api/add_to_history/<int:video_id>', methods=['POST'])
@login_required
def add_to_history(video_id):
    Video.query.get_or_404(video_id)
    existing = WatchHistory.query.filter_by(user_id=current_user.id, video_id=video_id).first()

    if existing:
        existing.watched_at = datetime.utcnow()
    else:
        db.session.add(WatchHistory(user_id=current_user.id, video_id=video_id))

    db.session.commit()

    return jsonify({'success': True})


@app.route('/subscriptions')
@login_required
def subscriptions():
    subs = Subscription.query.filter_by(subscriber_id=current_user.id).all()
    return render_template('subscriptions.html', channels=[User.query.get(sub.channel_id) for sub in subs])


@app.route('/uploads/videos/<filename>')
def uploaded_video(filename):
    return send_from_directory(app.config['VIDEO_FOLDER'], filename)


@app.route('/uploads/thumbnails/<filename>')
def uploaded_thumbnail(filename):
    return send_from_directory(app.config['THUMBNAIL_FOLDER'], filename or 'default_avatar.png')


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.before_request
def create_tables():
    if not hasattr(app, 'tables_created'):
        db.create_all()
        app.tables_created = True


def init_database():
    with app.app_context():
        try:
            db.create_all()
            print("Таблицы базы данных созданы")

            for user in User.query.all():
                create_default_playlists(user.id)

            print("Стандартные плейлисты созданы")
        except Exception as e:
            print(f"Ошибка при инициализации БД: {e}")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)