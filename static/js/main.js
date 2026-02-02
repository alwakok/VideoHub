// Основные функции JavaScript для VideoHUB

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всех интерактивных элементов

    // Управление видео-плеером
    initVideoPlayer();

    // Инициализация лайков
    initLikes();

    // Инициализация комментариев
    initComments();

    // Инициализация поиска
    initSearch();

    // Инициализация загрузки файлов
    initFileUploads();
});

// Видео плеер
function initVideoPlayer() {
    const video = document.getElementById('main-video');
    if (video) {
        // Автовоспроизведение при скролле
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Можно добавить автовоспроизведение при видимости
                }
            });
        }, { threshold: 0.5 });

        observer.observe(video);
    }
}

// Лайки
function initLikes() {
    const likeButtons = document.querySelectorAll('.like-btn');

    likeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const videoId = this.dataset.videoId;
            toggleLike(videoId, this);
        });
    });
}

function toggleLike(videoId, button) {
    fetch(`/like/${videoId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            button.classList.toggle('liked');
            const likeCount = button.querySelector('.like-count');
            if (likeCount) {
                likeCount.textContent = data.like_count;
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// Комментарии
function initComments() {
    const commentForm = document.getElementById('comment-form');

    if (commentForm) {
        commentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitComment(this);
        });
    }
}

function submitComment(form) {
    const videoId = form.dataset.videoId;
    const content = form.querySelector('#comment-input').value;

    if (!content.trim()) return;

    fetch(`/comment/${videoId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'content': content
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            addCommentToDOM(data.comment);
            form.reset();

            // Обновляем счетчик комментариев
            const commentsCount = document.getElementById('comments-count');
            if (commentsCount) {
                commentsCount.textContent = parseInt(commentsCount.textContent) + 1;
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function addCommentToDOM(comment) {
    const commentsList = document.getElementById('comments-list');

    // Убираем сообщение "нет комментариев"
    const noComments = commentsList.querySelector('.no-comments');
    if (noComments) {
        noComments.remove();
    }

    const commentHTML = `
        <div class="comment-item">
            <a href="/profile/${comment.author.username}" class="comment-avatar">
                <img src="${comment.author.avatar}" alt="${comment.author.username}">
            </a>
            <div class="comment-content">
                <div class="comment-header">
                    <a href="/profile/${comment.author.username}" class="comment-author">
                        ${comment.author.username}
                    </a>
                    <span class="comment-date">${comment.created_at}</span>
                </div>
                <p class="comment-text">${comment.content}</p>
            </div>
        </div>
    `;

    commentsList.insertAdjacentHTML('afterbegin', commentHTML);
}

// Поиск
function initSearch() {
    const searchInput = document.querySelector('.search-bar input');

    if (searchInput) {
        // Автозаполнение поиска
        searchInput.addEventListener('input', function() {
            if (this.value.length > 2) {
                // Здесь можно добавить автозаполнение
            }
        });

        // Поиск при нажатии Enter
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                this.closest('form').submit();
            }
        });
    }
}

// Загрузка файлов
function initFileUploads() {
    const fileInputs = document.querySelectorAll('input[type="file"]');

    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const fileName = this.files[0]?.name;
            if (fileName) {
                // Можно добавить отображение имени файла
            }
        });
    });
}

// Вспомогательные функции
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background-color: ${type === 'success' ? '#5CB85C' : '#D9534F'};
        color: white;
        border-radius: 8px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Добавляем стили для анимаций
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
