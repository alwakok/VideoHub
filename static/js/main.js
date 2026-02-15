// Основные функции JavaScript для VideoHUB

document.addEventListener('DOMContentLoaded', function() {
    initVideoPlayer();
    initLikes();
    initComments();
    initSearch();
    initFileUploads();
    initMobileMenu();
    initTheme();
    initUserMenu();
    initGuestMenu();
    initAvatarErrorHandler();
});

// Видео плеер
function initVideoPlayer() {
    const video = document.getElementById('main-video');
    if (video && typeof IntersectionObserver !== 'undefined') {
        new IntersectionObserver((entries) => {
            entries.forEach(entry => {});
        }, { threshold: 0.5 }).observe(video);
    }
}

// Лайки
function initLikes() {
    document.querySelectorAll('.like-btn, #like-btn, .remove-favorite').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const videoId = this.dataset.videoId || this.getAttribute('data-video-id');
            if (!videoId) return;

            fetch(`/like/${videoId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(res => res.json())
            .then(data => {
                this.classList.toggle('liked', data.liked);
                const count = this.querySelector('#like-count, .like-count');
                if (count) count.textContent = data.like_count;
            })
            .catch(console.error);
        });
    });
}

// Комментарии
function initComments() {
    const form = document.getElementById('comment-form');
    if (!form) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const videoId = this.dataset.videoId;
        const input = document.getElementById('comment-input');
        const content = input.value.trim();
        if (!content) return;

        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        submitBtn.disabled = true;

        fetch(`/comment/${videoId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ 'content': content })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                addCommentToDOM(data.comment);
                input.value = '';
                const count = document.getElementById('comments-count');
                if (count) count.textContent = parseInt(count.textContent) + 1;
            }
        })
        .catch(console.error)
        .finally(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        });
    });
}

function addCommentToDOM(comment) {
    const list = document.getElementById('comments-list');
    if (!list) return;

    const noComments = list.querySelector('.no-comments');
    if (noComments) noComments.remove();

    const html = `
        <div class="comment-item">
            <a href="/profile/${comment.author.username}" class="comment-avatar">
                <img src="${comment.author.avatar}" alt="${comment.author.username}">
            </a>
            <div class="comment-content">
                <div class="comment-header">
                    <a href="/profile/${comment.author.username}" class="comment-author">${comment.author.username}</a>
                    <span class="comment-date">${comment.created_at}</span>
                </div>
                <p class="comment-text">${comment.content}</p>
            </div>
        </div>
    `;
    list.insertAdjacentHTML('afterbegin', html);
}

// Поиск
function initSearch() {
    const input = document.querySelector('.search-bar input');
    if (input) {
        input.addEventListener('keypress', e => {
            if (e.key === 'Enter') e.target.closest('form').submit();
        });
    }
}

// Загрузка файлов
function initFileUploads() {
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', function() {
            if (this.files[0]) console.log('File selected:', this.files[0].name);
        });
    });
}

// Мобильное меню
function initMobileMenu() {
    const toggle = document.getElementById('mobile-search-toggle');
    const search = document.getElementById('mobile-search');

    if (toggle && search) {
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            search.classList.toggle('active');
        });

        document.addEventListener('click', (e) => {
            if (!search.contains(e.target) && !toggle.contains(e.target)) {
                search.classList.remove('active');
            }
        });
    }

    // Mobile sidebar toggle
    const sidebarToggle = document.querySelector('.mobile-sidebar-toggle');
    const sidebar = document.getElementById('sidebar');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('active');
        });
    }

    // Check screen size
    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
}

function checkScreenSize() {
    const mobileSearchToggle = document.getElementById('mobile-search-toggle');
    const desktopSearch = document.querySelector('.search-bar');
    const mobileSearch = document.getElementById('mobile-search');

    if (window.innerWidth <= 768) {
        if (mobileSearchToggle) mobileSearchToggle.style.display = 'flex';
        if (desktopSearch) desktopSearch.style.display = 'none';
        if (mobileSearch) mobileSearch.classList.remove('active');
    } else {
        if (mobileSearchToggle) mobileSearchToggle.style.display = 'none';
        if (desktopSearch) desktopSearch.style.display = 'block';
        if (mobileSearch) mobileSearch.classList.remove('active');
    }
}

// Тема
function initTheme() {
    const saved = localStorage.getItem('theme') || 'light';
    const isDark = saved === 'dark';
    document.body.classList.toggle('dark-theme', isDark);

    // Синхронизируем все переключатели
    document.querySelectorAll('#guest-theme-toggle, .theme-toggle input[type="checkbox"]').forEach(toggle => {
        if (toggle.type === 'checkbox') {
            toggle.checked = isDark;
        }
    });
}

// Универсальная функция переключения темы
window.toggleTheme = function(checked) {
    const isDark = checked !== undefined ? checked : document.body.classList.contains('dark-theme');
    document.body.classList.toggle('dark-theme', !isDark);
    const newState = !isDark;
    localStorage.setItem('theme', newState ? 'dark' : 'light');

    // Синхронизируем все переключатели темы
    document.querySelectorAll('#guest-theme-toggle, .theme-toggle input[type="checkbox"]').forEach(toggle => {
        if (toggle.type === 'checkbox') {
            toggle.checked = newState;
        }
    });

    if (window.currentUser?.is_authenticated) {
        fetch('/api/theme', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ theme: newState ? 'dark' : 'light' })
        }).catch(console.error);
    }
};

// Гостевой меню
function initGuestMenu() {
    const settingsBtn = document.getElementById('guest-settings-btn');
    const settingsModal = document.getElementById('guest-settings-modal');
    const themeToggle = document.getElementById('guest-theme-toggle');

    if (!settingsBtn || !settingsModal) return;

    // Открытие/закрытие модального окна
    settingsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        settingsModal.classList.toggle('active');
    });

    // Закрытие при клике вне
    document.addEventListener('click', (e) => {
        if (!settingsModal.contains(e.target) && !settingsBtn.contains(e.target)) {
            settingsModal.classList.remove('active');
        }
    });

    // Переключение темы для гостей
    if (themeToggle) {
        // Устанавливаем начальное состояние
        const savedTheme = localStorage.getItem('theme') || 'light';
        themeToggle.checked = savedTheme === 'dark';

        themeToggle.addEventListener('change', function() {
            const isDark = this.checked;
            document.body.classList.toggle('dark-theme', isDark);
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        });
    }
}

// User menu
function initUserMenu() {
    const userMenu = document.querySelector('.user-menu');
    if (!userMenu) return;

    const dropdown = userMenu.querySelector('.dropdown');

    userMenu.addEventListener('mouseenter', () => {
        if (window.innerWidth > 768) dropdown.style.display = 'block';
    });

    userMenu.addEventListener('mouseleave', () => {
        if (window.innerWidth > 768) dropdown.style.display = 'none';
    });

    userMenu.addEventListener('click', (e) => {
        if (window.innerWidth <= 768) {
            e.preventDefault();
            dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
        }
    });
}

// Avatar error handler
function initAvatarErrorHandler() {
    document.querySelectorAll('img[src*="thumbnails"]').forEach(img => {
        img.addEventListener('error', function() {
            this.src = '/uploads/thumbnails/default_avatar.png';
        });
    });
}

// Вспомогательные функции
window.showNotification = function(message, type = 'info') {
    const colors = { success: '#5CB85C', error: '#D9534F', info: '#B380E6' };
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed; top: 20px; right: 20px; padding: 15px 20px;
        background: ${colors[type] || colors.info}; color: white; border-radius: 8px;
        z-index: 1000; animation: slideIn 0.3s ease; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    `;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
};

// Добавляем стили для анимаций
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);