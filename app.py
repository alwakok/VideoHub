import os
import random
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
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


# ========== МОДЕЛИ БАЗЫ ДАННЫХ ==========

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

    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(500), nullable=True)
    ban_expires = db.Column(db.DateTime, nullable=True)

    videos = db.relationship('Video', backref='author', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy=True, cascade='all, delete-orphan')
    playlists = db.relationship('Playlist', backref='user', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade='all, delete-orphan')
    watch_history = db.relationship('WatchHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', foreign_keys='Subscription.subscriber_id', backref='subscriber',
                                    lazy=True, cascade='all, delete-orphan')
    subscribers = db.relationship('Subscription', foreign_keys='Subscription.channel_id', backref='channel', lazy=True,
                                  cascade='all, delete-orphan')
    bans_issued = db.relationship('Ban', foreign_keys='Ban.admin_id', backref='admin', lazy=True,
                                  cascade='all, delete-orphan')
    bans_received = db.relationship('Ban', foreign_keys='Ban.user_id', backref='user', lazy=True,
                                    cascade='all, delete-orphan')
    created_rooms = db.relationship('WatchRoom', foreign_keys='WatchRoom.created_by', backref='creator', lazy=True,
                                    cascade='all, delete-orphan')
    room_participations = db.relationship('RoomParticipant', backref='user', lazy=True, cascade='all, delete-orphan')
    room_messages = db.relationship('RoomMessage', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_banned_active(self):
        if not self.is_banned:
            return False
        if self.ban_expires and self.ban_expires < datetime.utcnow():
            self.is_banned = False
            self.ban_reason = None
            self.ban_expires = None
            db.session.commit()
            return False
        return True


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
    watch_histories = db.relationship('WatchHistory', backref='video', lazy=True, cascade='all, delete-orphan')
    playlist_videos = db.relationship('PlaylistVideo', backref='video', lazy=True, cascade='all, delete-orphan')
    favorites_ref = db.relationship('Favorite', backref='video', lazy=True, cascade='all, delete-orphan')
    rooms = db.relationship('WatchRoom', backref='video', lazy=True)


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


class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('subscriber_id', 'channel_id', name='unique_subscription'),)


class Ban(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    duration_type = db.Column(db.String(20), nullable=False)
    duration_hours = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    unbanned_at = db.Column(db.DateTime, nullable=True)
    unbanned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    unban_reason = db.Column(db.String(500), nullable=True)


class WatchRoom(db.Model):
    """Комната для совместного просмотра"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    max_participants = db.Column(db.Integer, default=10)
    current_video_time = db.Column(db.Float, default=0)
    is_playing = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime, default=datetime.utcnow)
    room_password = db.Column(db.String(200), nullable=True)  # хеш пароля

    participants = db.relationship('RoomParticipant', backref='room', lazy=True, cascade='all, delete-orphan')
    messages = db.relationship('RoomMessage', backref='room', lazy=True, cascade='all, delete-orphan')

class RoomParticipant(db.Model):
    """Участник комнаты"""
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('watch_room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('room_id', 'user_id', name='unique_participant'),)


class RoomMessage(db.Model):
    """Сообщение в комнате"""
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('watch_room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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


# ========== МАРШРУТЫ ==========

@app.before_request
def check_if_banned():
    if current_user.is_authenticated and current_user.is_banned_active():
        if request.endpoint not in ['banned', 'logout', 'static', 'uploaded_thumbnail', 'uploaded_video']:
            return redirect(url_for('banned'))


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


@app.route('/faq')
def faq():
    return render_template('faq.html')


# ========== СОВМЕСТНЫЙ ПРОСМОТР ==========

@app.route('/watch-together')
def watch_together():
    """Страница совместного просмотра"""
    rooms = WatchRoom.query.order_by(WatchRoom.created_at.desc()).all()
    return render_template('watch_together.html', rooms=rooms)

@app.route('/watch-together/create', methods=['GET', 'POST'])
@login_required
def create_watch_room():
    """Создание комнаты для совместного просмотра"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_public = request.form.get('is_public') == 'on'
        max_participants = int(request.form.get('max_participants', 10))
        video_id = request.form.get('video_id')
        room_password = request.form.get('room_password', '').strip()

        if not name:
            flash('Название комнаты обязательно', 'error')
            return redirect(request.url)

        room = WatchRoom(
            name=name,
            description=description,
            created_by=current_user.id,
            is_public=is_public,
            max_participants=max_participants
        )

        if video_id:
            # Проверяем, существует ли видео
            video = Video.query.get(video_id)
            if video:
                room.video_id = int(video_id)

        if room_password:
            room.room_password = generate_password_hash(room_password)
            room.is_public = False  # Если есть пароль, комната автоматически приватная

        db.session.add(room)
        db.session.commit()

        participant = RoomParticipant(
            room_id=room.id,
            user_id=current_user.id
        )
        db.session.add(participant)
        db.session.commit()

        flash('Комната создана!', 'success')
        return redirect(url_for('watch_room', room_id=room.id))

    # Получаем все видео (а не только видео текущего пользователя)
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return render_template('create_watch_room.html', videos=videos)

@app.route('/watch-room/<int:room_id>')
@login_required
def watch_room(room_id):
    """Страница комнаты для совместного просмотра"""
    room = WatchRoom.query.get_or_404(room_id)

    participants_count = RoomParticipant.query.filter_by(room_id=room_id).count()
    if participants_count >= room.max_participants:
        flash('Комната заполнена', 'error')
        return redirect(url_for('watch_together'))

    participant = RoomParticipant.query.filter_by(room_id=room_id, user_id=current_user.id).first()
    if not participant:
        participant = RoomParticipant(room_id=room_id, user_id=current_user.id)
        db.session.add(participant)
        db.session.commit()

    participants = RoomParticipant.query.filter_by(room_id=room_id).all()
    messages = RoomMessage.query.filter_by(room_id=room_id).order_by(RoomMessage.created_at.desc()).limit(50).all()
    messages.reverse()

    return render_template('watch_room.html',
                           room=room,
                           participants=participants,
                           messages=messages)


@app.route('/api/watch-room/<int:room_id>/sync', methods=['POST'])
@login_required
def sync_watch_room(room_id):
    """Синхронизация состояния комнаты"""
    room = WatchRoom.query.get_or_404(room_id)

    participant = RoomParticipant.query.filter_by(room_id=room_id, user_id=current_user.id).first()
    if not participant:
        return jsonify({'error': 'Вы не участник этой комнаты'}), 403

    data = request.get_json()

    if 'current_time' in data:
        room.current_video_time = data['current_time']
    if 'is_playing' in data:
        room.is_playing = data['is_playing']

    room.last_sync = datetime.utcnow()
    participant.last_active = datetime.utcnow()
    db.session.commit()

    active_participants = RoomParticipant.query.filter_by(room_id=room_id).all()
    active_users = [{
        'id': p.user.id,
        'username': p.user.username,
        'avatar': url_for('uploaded_thumbnail', filename=p.user.avatar),
        'is_creator': p.user_id == room.created_by
    } for p in active_participants]

    return jsonify({
        'success': True,
        'current_time': room.current_video_time,
        'is_playing': room.is_playing,
        'participants': active_users
    })


@app.route('/api/watch-room/<int:room_id>/state')
@login_required
def get_watch_room_state(room_id):
    """Получение текущего состояния комнаты"""
    room = WatchRoom.query.get_or_404(room_id)

    participant = RoomParticipant.query.filter_by(room_id=room_id, user_id=current_user.id).first()
    if not participant:
        return jsonify({'error': 'Вы не участник этой комнаты'}), 403

    participant.last_active = datetime.utcnow()
    db.session.commit()

    active_participants = RoomParticipant.query.filter_by(room_id=room_id).all()
    active_users = [{
        'id': p.user.id,
        'username': p.user.username,
        'avatar': url_for('uploaded_thumbnail', filename=p.user.avatar),
        'is_creator': p.user_id == room.created_by
    } for p in active_participants]

    video_info = None
    if room.video_id:
        video = Video.query.get(room.video_id)
        if video:
            video_info = {
                'id': video.id,
                'title': video.title,
                'thumbnail': url_for('uploaded_thumbnail', filename=video.thumbnail),
                'filename': video.filename,
                'duration': video.duration
            }

    return jsonify({
        'success': True,
        'room': {
            'id': room.id,
            'name': room.name,
            'description': room.description,
            'is_public': room.is_public,
            'max_participants': room.max_participants,
            'current_time': room.current_video_time,
            'is_playing': room.is_playing,
            'video': video_info,
            'created_by': room.created_by,
            'creator_username': room.creator.username
        },
        'participants': active_users,
        'current_user_id': current_user.id
    })


@app.route('/api/watch-room/<int:room_id>/leave', methods=['POST'])
@login_required
def leave_watch_room(room_id):
    """Покинуть комнату"""
    room = WatchRoom.query.get_or_404(room_id)

    participant = RoomParticipant.query.filter_by(room_id=room_id, user_id=current_user.id).first()
    if participant:
        db.session.delete(participant)
        db.session.commit()

    remaining = RoomParticipant.query.filter_by(room_id=room_id).count()
    if remaining == 0:
        db.session.delete(room)
        db.session.commit()

    return jsonify({'success': True})


@app.route('/api/watch-room/<int:room_id>/message', methods=['POST'])
@login_required
def send_room_message(room_id):
    """Отправить сообщение в комнату"""
    room = WatchRoom.query.get_or_404(room_id)
    data = request.get_json()
    message_text = data.get('message', '').strip()

    if not message_text:
        return jsonify({'error': 'Сообщение не может быть пустым'}), 400

    participant = RoomParticipant.query.filter_by(room_id=room_id, user_id=current_user.id).first()
    if not participant:
        return jsonify({'error': 'Вы не участник этой комнаты'}), 403

    message = RoomMessage(
        room_id=room_id,
        user_id=current_user.id,
        message=message_text
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': {
            'id': message.id,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'avatar': url_for('uploaded_thumbnail', filename=current_user.avatar)
            },
            'message': message.message,
            'created_at': message.created_at.strftime('%H:%M')
        }
    })


@app.route('/api/watch-room/<int:room_id>/messages')
@login_required
def get_room_messages(room_id):
    """Получить последние сообщения в комнате"""
    room = WatchRoom.query.get_or_404(room_id)

    participant = RoomParticipant.query.filter_by(room_id=room_id, user_id=current_user.id).first()
    if not participant:
        return jsonify({'error': 'Вы не участник этой комнаты'}), 403

    last_id = request.args.get('last_id', 0, type=int)

    if last_id > 0:
        messages = RoomMessage.query.filter(
            RoomMessage.room_id == room_id,
            RoomMessage.id > last_id
        ).order_by(RoomMessage.created_at.asc()).all()
    else:
        messages = RoomMessage.query.filter_by(room_id=room_id).order_by(RoomMessage.created_at.asc()).limit(50).all()

    return jsonify({
        'success': True,
        'messages': [{
            'id': m.id,
            'user': {
                'id': m.user.id,
                'username': m.user.username,
                'avatar': url_for('uploaded_thumbnail', filename=m.user.avatar)
            },
            'message': m.message,
            'created_at': m.created_at.strftime('%H:%M')
        } for m in messages]
    })


@app.route('/api/watch-room/<int:room_id>/change_video', methods=['POST'])
@login_required
def change_room_video(room_id):
    """Сменить видео в комнате"""
    room = WatchRoom.query.get_or_404(room_id)

    if room.created_by != current_user.id:
        return jsonify({'error': 'Только создатель комнаты может менять видео'}), 403

    data = request.get_json()
    video_id = data.get('video_id')

    if video_id:
        video = Video.query.get(video_id)
        if not video:
            return jsonify({'error': 'Видео не найдено'}), 404
        room.video_id = video_id
    else:
        room.video_id = None

    room.current_video_time = 0
    room.is_playing = False
    db.session.commit()

    return jsonify({'success': True})


@app.route('/api/user/videos')
@login_required
def get_user_videos():
    """API для получения списка ВСЕХ видео (для выбора в комнате)"""
    # Возвращаем все видео, отсортированные по дате
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return jsonify([{
        'id': v.id,
        'title': v.title,
        'thumbnail': url_for('uploaded_thumbnail', filename=v.thumbnail),
        'views': v.views,
        'duration': v.duration,
        'author': v.author.username
    } for v in videos])


# ========== ОСТАЛЬНЫЕ МАРШРУТЫ ==========

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
    """Лайк/дизлайк видео"""
    try:
        video = Video.query.get_or_404(video_id)

        # Проверяем, есть ли уже лайк от этого пользователя
        existing_like = Like.query.filter_by(
            user_id=current_user.id,
            video_id=video_id
        ).first()

        if existing_like:
            # Удаляем лайк
            db.session.delete(existing_like)
            liked = False
            message = 'Лайк убран'
        else:
            # Добавляем лайк
            new_like = Like(user_id=current_user.id, video_id=video_id)
            db.session.add(new_like)
            liked = True
            message = 'Видео понравилось!'

        db.session.commit()

        # Получаем актуальное количество лайков
        like_count = Like.query.filter_by(video_id=video_id).count()

        return jsonify({
            'success': True,
            'liked': liked,
            'like_count': like_count,
            'message': message
        })

    except IntegrityError:
        # Если возникла ошибка уникальности (дубликат), обрабатываем её
        db.session.rollback()

        # Проверяем еще раз, возможно лайк уже был добавлен другим запросом
        existing_like = Like.query.filter_by(
            user_id=current_user.id,
            video_id=video_id
        ).first()

        if existing_like:
            # Если лайк есть, удаляем его (как toggle)
            db.session.delete(existing_like)
            liked = False
            message = 'Лайк убран'
        else:
            # Если нет - добавляем
            new_like = Like(user_id=current_user.id, video_id=video_id)
            db.session.add(new_like)
            liked = True
            message = 'Видео понравилось!'

        db.session.commit()

        like_count = Like.query.filter_by(video_id=video_id).count()

        return jsonify({
            'success': True,
            'liked': liked,
            'like_count': like_count,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при обработке лайка: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        WatchHistory.query.filter_by(video_id=video_id).delete()
        Like.query.filter_by(video_id=video_id).delete()
        Comment.query.filter_by(video_id=video_id).delete()
        PlaylistVideo.query.filter_by(video_id=video_id).delete()
        Favorite.query.filter_by(video_id=video_id).delete()

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
        print(f"Ошибка при удалении видео: {str(e)}")
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

        if username.lower() == 'admin':
            errors.append('Это имя пользователя недоступно')

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


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    videos = []

    if query:
        query_lower = query.lower()
        all_videos = Video.query.all()

        for video in all_videos:
            title_lower = video.title.lower() if video.title else ''
            desc_lower = video.description.lower() if video.description else ''
            tags_lower = video.tags.lower() if video.tags else ''

            if (query_lower in title_lower or
                    query_lower in desc_lower or
                    query_lower in tags_lower):
                videos.append(video)

        videos.sort(key=lambda x: x.created_at, reverse=True)

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
    favorite_playlist = Playlist.query.filter_by(
        user_id=current_user.id,
        name="Избранное"
    ).first()

    if favorite_playlist:
        videos = [pv.video for pv in favorite_playlist.videos]
    else:
        videos = []

    return render_template('favorites.html', videos=videos)


@app.route('/favorite/<int:video_id>', methods=['POST'])
@login_required
def toggle_favorite(video_id):
    """Добавить/удалить видео из избранного"""
    try:
        video = Video.query.get_or_404(video_id)

        # Получаем или создаем плейлист "Избранное"
        favorite_playlist = Playlist.query.filter_by(
            user_id=current_user.id,
            name="Избранное"
        ).first()

        if not favorite_playlist:
            favorite_playlist = Playlist(
                user_id=current_user.id,
                name="Избранное",
                description="Мои любимые видео",
                is_public=False
            )
            db.session.add(favorite_playlist)
            db.session.commit()

        # Проверяем, есть ли видео в избранном
        existing = PlaylistVideo.query.filter_by(
            playlist_id=favorite_playlist.id,
            video_id=video_id
        ).first()

        if existing:
            # Удаляем из избранного
            db.session.delete(existing)
            favorited = False
            message = 'Видео удалено из избранного'
        else:
            # Добавляем в избранное
            playlist_video = PlaylistVideo(
                playlist_id=favorite_playlist.id,
                video_id=video_id
            )
            db.session.add(playlist_video)
            favorited = True
            message = 'Видео добавлено в избранное'

        db.session.commit()

        # Получаем актуальное количество видео в избранном
        favorites_count = PlaylistVideo.query.filter_by(
            playlist_id=favorite_playlist.id
        ).count()

        return jsonify({
            'success': True,
            'favorited': favorited,
            'message': message,
            'favorites_count': favorites_count
        })

    except IntegrityError:
        # Если возникла ошибка уникальности, обрабатываем её
        db.session.rollback()

        favorite_playlist = Playlist.query.filter_by(
            user_id=current_user.id,
            name="Избранное"
        ).first()

        if favorite_playlist:
            existing = PlaylistVideo.query.filter_by(
                playlist_id=favorite_playlist.id,
                video_id=video_id
            ).first()

            if existing:
                # Удаляем из избранного
                db.session.delete(existing)
                favorited = False
                message = 'Видео удалено из избранного'
            else:
                # Добавляем в избранное
                playlist_video = PlaylistVideo(
                    playlist_id=favorite_playlist.id,
                    video_id=video_id
                )
                db.session.add(playlist_video)
                favorited = True
                message = 'Видео добавлено в избранное'

            db.session.commit()

            favorites_count = PlaylistVideo.query.filter_by(
                playlist_id=favorite_playlist.id
            ).count()

            return jsonify({
                'success': True,
                'favorited': favorited,
                'message': message,
                'favorites_count': favorites_count
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Ошибка при работе с избранным'
            }), 500

    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при работе с избранным: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/check-favorite/<int:video_id>')
@login_required
def check_favorite(video_id):
    favorite_playlist = Playlist.query.filter_by(
        user_id=current_user.id,
        name="Избранное"
    ).first()

    if not favorite_playlist:
        return jsonify({'is_favorite': False})

    exists = PlaylistVideo.query.filter_by(
        playlist_id=favorite_playlist.id,
        video_id=video_id
    ).first() is not None

    return jsonify({'is_favorite': exists})


@app.route('/playlists')
@login_required
def playlists():
    return render_template('playlists.html', playlists=current_user.playlists)


@app.route('/playlist/create', methods=['POST'])
@login_required
def create_playlist():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    is_public = request.form.get('is_public') == 'on'

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

    flash('Плейлист успешно создан!', 'success')
    return jsonify({
        'success': True,
        'playlist': {
            'id': playlist.id,
            'name': playlist.name,
            'description': playlist.description,
            'is_public': playlist.is_public
        }
    })


@app.route('/playlist/delete/<int:playlist_id>', methods=['POST'])
@login_required
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    if playlist.user_id != current_user.id:
        return jsonify({'error': 'Недостаточно прав'}), 403

    if playlist.name == "Избранное":
        return jsonify({'error': 'Нельзя удалить стандартный плейлист "Избранное"'}), 400

    try:
        db.session.delete(playlist)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/playlist/toggle_public/<int:playlist_id>', methods=['POST'])
@login_required
def toggle_playlist_public(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    if playlist.user_id != current_user.id:
        return jsonify({'error': 'Недостаточно прав'}), 403

    playlist.is_public = not playlist.is_public
    db.session.commit()

    return jsonify({
        'success': True,
        'is_public': playlist.is_public
    })


@app.route('/playlist/<int:playlist_id>')
@login_required
def playlist_detail(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    if not playlist.is_public and playlist.user_id != current_user.id:
        flash('Этот плейлист приватный', 'error')
        return redirect(url_for('playlists'))

    videos = [pv.video for pv in playlist.videos]

    return render_template('playlist_detail.html', playlist=playlist, videos=videos)


@app.route('/api/user/playlists')
@login_required
def get_user_playlists():
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'is_public': p.is_public,
        'video_count': len(p.videos)
    } for p in playlists])


@app.route('/playlist/<int:playlist_id>/add_video', methods=['POST'])
@login_required
def add_video_to_playlist(playlist_id):
    data = request.get_json()
    video_id = data.get('video_id')

    if not video_id:
        return jsonify({'error': 'ID видео не указан'}), 400

    playlist = Playlist.query.get_or_404(playlist_id)
    video = Video.query.get_or_404(video_id)

    if playlist.user_id != current_user.id:
        return jsonify({'error': 'Недостаточно прав'}), 403

    existing = PlaylistVideo.query.filter_by(
        playlist_id=playlist_id,
        video_id=video_id
    ).first()

    if existing:
        return jsonify({'error': 'Видео уже в этом плейлисте'}), 400

    playlist_video = PlaylistVideo(
        playlist_id=playlist_id,
        video_id=video_id
    )
    db.session.add(playlist_video)

    if playlist.thumbnail == 'default-playlist.png' and video.thumbnail:
        playlist.thumbnail = video.thumbnail

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Видео добавлено в плейлист "{playlist.name}"'
    })


@app.route('/playlist/<int:playlist_id>/remove_video/<int:video_id>', methods=['POST'])
@login_required
def remove_video_from_playlist(playlist_id, video_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    if playlist.user_id != current_user.id:
        return jsonify({'error': 'Недостаточно прав'}), 403

    playlist_video = PlaylistVideo.query.filter_by(
        playlist_id=playlist_id,
        video_id=video_id
    ).first()

    if not playlist_video:
        return jsonify({'error': 'Видео не найдено в плейлисте'}), 404

    db.session.delete(playlist_video)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/watch_history')
@login_required
def watch_history():
    history = WatchHistory.query.filter_by(user_id=current_user.id).order_by(WatchHistory.watched_at.desc()).limit(
        50).all()
    return render_template('history.html', videos=[h.video for h in history if h.video])


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


@app.route('/subscribe/<int:channel_id>', methods=['POST'])
@login_required
def subscribe(channel_id):
    channel = User.query.get_or_404(channel_id)

    if current_user.id == channel_id:
        return jsonify({'error': 'Нельзя подписаться на свой канал'}), 400

    existing = Subscription.query.filter_by(
        subscriber_id=current_user.id,
        channel_id=channel_id
    ).first()

    if existing:
        db.session.delete(existing)
        subscribed = False
        message = f'Вы отписались от канала {channel.username}'
    else:
        db.session.add(Subscription(subscriber_id=current_user.id, channel_id=channel_id))
        subscribed = True
        message = f'Вы подписались на канал {channel.username}'

    db.session.commit()

    subscribers_count = Subscription.query.filter_by(channel_id=channel_id).count()

    return jsonify({
        'success': True,
        'subscribed': subscribed,
        'subscribers_count': subscribers_count,
        'message': message
    })


@app.route('/api/channel/<int:channel_id>/subscription-status')
@login_required
def get_subscription_status(channel_id):
    if current_user.is_authenticated:
        subscribed = Subscription.query.filter_by(
            subscriber_id=current_user.id,
            channel_id=channel_id
        ).first() is not None
    else:
        subscribed = False

    subscribers_count = Subscription.query.filter_by(channel_id=channel_id).count()

    return jsonify({
        'subscribed': subscribed,
        'subscribers_count': subscribers_count
    })


# ========== АДМИН ПАНЕЛЬ ==========

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('У вас нет доступа к этой странице', 'error')
        return redirect(url_for('index'))

    users = User.query.all()
    videos = Video.query.all()
    comments = Comment.query.all()
    ban_history = Ban.query.order_by(Ban.created_at.desc()).all()

    return render_template('admin.html',
                           users=users,
                           videos=videos,
                           comments=comments,
                           ban_history=ban_history,
                           total_users=len(users),
                           total_videos=len(videos),
                           total_comments=len(comments),
                           banned_users=User.query.filter_by(is_banned=True).count())


@app.route('/admin/ban', methods=['POST'])
@login_required
def admin_ban():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    user_id = request.form.get('user_id')
    reason = request.form.get('reason')
    ban_type = request.form.get('ban_type')
    duration = request.form.get('duration', type=int)

    if not user_id or not reason:
        return jsonify({'error': 'Не все поля заполнены'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    if user.is_admin:
        return jsonify({'error': 'Нельзя забанить администратора'}), 400

    expires_at = None
    if ban_type == 'temporary' and duration:
        expires_at = datetime.utcnow() + timedelta(hours=duration)

    ban = Ban(
        user_id=user.id,
        admin_id=current_user.id,
        reason=reason,
        duration_type='permanent' if ban_type == 'permanent' else 'temporary',
        duration_hours=duration if ban_type == 'temporary' else None,
        expires_at=expires_at
    )

    user.is_banned = True
    user.ban_reason = reason
    user.ban_expires = expires_at

    db.session.add(ban)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/admin/unban', methods=['POST'])
@login_required
def admin_unban():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    user_id = request.form.get('user_id')
    reason = request.form.get('reason')

    if not user_id:
        return jsonify({'error': 'Не указан пользователь'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    active_ban = Ban.query.filter_by(user_id=user_id, is_active=True).first()
    if active_ban:
        active_ban.is_active = False
        active_ban.unbanned_at = datetime.utcnow()
        active_ban.unbanned_by = current_user.id
        active_ban.unban_reason = reason

    user.is_banned = False
    user.ban_reason = None
    user.ban_expires = None

    db.session.commit()

    return jsonify({'success': True})


@app.route('/admin/delete/video/<int:video_id>', methods=['POST'])
@login_required
def admin_delete_video(video_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    video = Video.query.get(video_id)
    if not video:
        return jsonify({'error': 'Видео не найдено'}), 404

    try:
        WatchHistory.query.filter_by(video_id=video_id).delete()
        Like.query.filter_by(video_id=video_id).delete()
        Comment.query.filter_by(video_id=video_id).delete()
        PlaylistVideo.query.filter_by(video_id=video_id).delete()
        Favorite.query.filter_by(video_id=video_id).delete()

        video_path = os.path.join(app.config['VIDEO_FOLDER'], video.filename)
        if os.path.exists(video_path):
            os.remove(video_path)

        if video.thumbnail and video.thumbnail != 'default-thumbnail.jpg':
            thumb_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

        db.session.delete(video)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при удалении видео: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/delete/comment/<int:comment_id>', methods=['POST'])
@login_required
def admin_delete_comment(comment_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'error': 'Комментарий не найден'}), 404

    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f"Ошибка при удалении комментария: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/banned')
@login_required
def banned():
    if not current_user.is_banned_active():
        return redirect(url_for('index'))

    ban = Ban.query.filter_by(user_id=current_user.id, is_active=True).first()

    return render_template('banned.html', ban=ban)


@app.route('/about')
def about_project():
    return render_template('about_project.html')


@app.route('/legal')
def legal_info():
    return render_template('legal_info.html')


@app.route('/support')
def support():
    return render_template('support.html')


@app.route('/api/playlist/check_video/<int:video_id>')
@login_required
def check_video_in_playlists(video_id):
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()

    playlist_ids = []
    for playlist in playlists:
        existing = PlaylistVideo.query.filter_by(
            playlist_id=playlist.id,
            video_id=video_id
        ).first()
        if existing:
            playlist_ids.append(playlist.id)

    return jsonify({'playlist_ids': playlist_ids})


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


def init_database():
    with app.app_context():
        try:
            db.create_all()
            print("Таблицы базы данных созданы")

            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@videohub.ru',
                    avatar='default_avatar.png',
                    is_admin=True,
                    terms_accepted_at=datetime.utcnow()
                )
                admin.set_password('adminadmin')
                db.session.add(admin)
                db.session.commit()
                print("Администратор создан (логин: admin, пароль: adminadmin)")

            for user in User.query.all():
                create_default_playlists(user.id)

            print("Стандартные плейлисты созданы")
        except Exception as e:
            print(f"Ошибка при инициализации БД: {e}")



@app.route('/api/watch-room/<int:room_id>/check_password', methods=['POST'])
def check_room_password(room_id):
    """Проверить пароль для входа в комнату"""
    room = WatchRoom.query.get_or_404(room_id)
    data = request.get_json()
    password = data.get('password')

    if room.room_password:
        if not password or not check_password_hash(room.room_password, password):
            return jsonify({'error': 'Неверный пароль'}), 403

    return jsonify({'success': True})


@app.route('/watch-room/<int:room_id>/join', methods=['GET', 'POST'])
@login_required
def join_watch_room(room_id):
    """Страница входа в комнату с паролем"""
    room = WatchRoom.query.get_or_404(room_id)

    if request.method == 'POST':
        password = request.form.get('password')

        if room.room_password:
            if not password or not check_password_hash(room.room_password, password):
                flash('Неверный пароль', 'error')
                return redirect(request.url)

        # Проверяем не полная ли комната
        participants_count = RoomParticipant.query.filter_by(room_id=room_id).count()
        if participants_count >= room.max_participants:
            flash('Комната заполнена', 'error')
            return redirect(url_for('watch_together'))

        # Добавляем пользователя в комнату
        participant = RoomParticipant.query.filter_by(room_id=room_id, user_id=current_user.id).first()
        if not participant:
            participant = RoomParticipant(room_id=room_id, user_id=current_user.id)
            db.session.add(participant)
            db.session.commit()

        return redirect(url_for('watch_room', room_id=room_id))

    return render_template('join_watch_room.html', room=room)


@app.route('/api/watch-room/<int:room_id>/set_password', methods=['POST'])
@login_required
def set_room_password(room_id):
    """Установить пароль для комнаты"""
    room = WatchRoom.query.get_or_404(room_id)

    if room.created_by != current_user.id:
        return jsonify({'error': 'Только создатель комнаты может установить пароль'}), 403

    data = request.get_json()
    password = data.get('password')

    if password:
        room.room_password = generate_password_hash(password)
        room.is_public = False
    else:
        room.room_password = None

    db.session.commit()

    return jsonify({'success': True})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_database()
    app.run(host='0.0.0.0', port=5001, debug=True)