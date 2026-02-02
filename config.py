import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///videohub.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    UPLOAD_FOLDER = "static/uploads"
    VIDEO_FOLDER = "static/uploads/videos"
    THUMBNAIL_FOLDER = "static/uploads/thumbnails"
    ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "webm"}
