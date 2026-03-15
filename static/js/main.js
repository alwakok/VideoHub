// Основные функции JavaScript для VideoHUB

(function() {
    'use strict';

    let isSubmitting = false;

    function init() {
        initLikes();
        initComments();
        initMobileMenu();
        initTheme();
        initGuestMenu();
        initAvatarErrorHandler();
        initFileUploads();
        initSubscribeButtons();
        initShareButtons();
        initFavoriteButtons();
        initSidebarScroll();
        initActiveFooterLinks(); // Добавьте эту строку
    }

    // Функция для показа уведомлений
    window.showNotification = function(message, type = 'info') {
        const colors = {
            success: '#5CB85C',
            error: '#D9534F',
            info: '#B380E6',
            warning: '#FFA500'
        };

        // Удаляем предыдущее уведомление
        const oldNotification = document.querySelector('.notification');
        if (oldNotification) {
            oldNotification.remove();
        }

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.backgroundColor = colors[type] || colors.info;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    };

    // Лайки
    function initLikes() {
        document.querySelectorAll('.like-btn, #like-btn').forEach(button => {
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

                    window.showNotification(
                        data.liked ? '❤️ Видео понравилось!' : 'Лайк убран',
                        'success'
                    );
                })
                .catch(() => window.showNotification('Ошибка при оценке видео', 'error'));
            });
        });
    }

    // Избранное
    function initFavoriteButtons() {
        document.querySelectorAll('#favorite-btn, .remove-favorite').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const videoId = this.dataset.videoId || this.getAttribute('data-video-id');
                if (!videoId) return;

                fetch(`/favorite/${videoId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(res => res.json())
                .then(data => {
                    if (this.id === 'favorite-btn') {
                        if (data.favorited) {
                            this.innerHTML = '<i class="fas fa-star"></i> <span>В избранном</span>';
                            this.classList.add('liked');
                            window.showNotification('⭐ Добавлено в избранное', 'success');
                        } else {
                            this.innerHTML = '<i class="fas fa-star"></i> <span>В избранное</span>';
                            this.classList.remove('liked');
                            window.showNotification('Удалено из избранного', 'info');
                        }
                    } else if (data.favorited === false) {
                        const card = this.closest('.video-card');
                        if (card) {
                            card.remove();
                            window.showNotification('Удалено из избранного', 'info');
                        }
                    }
                })
                .catch(() => window.showNotification('Ошибка при добавлении в избранное', 'error'));
            });
        });
    }

    // Комментарии
    function initComments() {
        const form = document.getElementById('comment-form');
        if (!form) return;

        // Удаляем старые обработчики
        const newForm = form.cloneNode(true);
        form.parentNode.replaceChild(newForm, form);

        newForm.addEventListener('submit', function(e) {
            e.preventDefault();

            if (isSubmitting) return;

            const videoId = this.dataset.videoId;
            const input = document.getElementById('comment-input');
            const content = input.value.trim();
            const submitBtn = this.querySelector('button[type="submit"]');

            if (!content) {
                window.showNotification('Введите текст комментария', 'warning');
                return;
            }

            isSubmitting = true;
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
            submitBtn.disabled = true;

            const formData = new FormData();
            formData.append('content', content);

            fetch(`/comment/${videoId}`, {
                method: 'POST',
                body: formData
            })
            .then(res => {
                if (!res.ok) throw new Error('Ошибка сервера');
                return res.json();
            })
            .then(data => {
                if (data.success && data.comment) {
                    addCommentToDOM(data.comment);
                    input.value = '';

                    const count = document.getElementById('comments-count');
                    if (count) {
                        count.textContent = parseInt(count.textContent) + 1;
                    }

                    window.showNotification('Комментарий добавлен', 'success');
                }
            })
            .catch(() => window.showNotification('Ошибка при добавлении комментария', 'error'))
            .finally(() => {
                isSubmitting = false;
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

        if (list.firstChild) {
            list.insertAdjacentHTML('afterbegin', html);
        } else {
            list.innerHTML = html;
        }
    }

    // Подписки
    function initSubscribeButtons() {
        document.querySelectorAll('.subscribe-btn').forEach(btn => {
            const channelId = btn.dataset.channelId || btn.dataset.userId;

            if (channelId) {
                fetch(`/api/channel/${channelId}/subscription-status`)
                    .then(res => res.json())
                    .then(data => {
                        if (data.subscribed) {
                            btn.classList.add('subscribed');
                            btn.innerHTML = '<i class="fas fa-user-check"></i> Вы подписаны';
                        }

                        const subscribersSpan = document.getElementById('subscribers-count-value');
                        if (subscribersSpan) {
                            subscribersSpan.textContent = data.subscribers_count;
                        }
                    })
                    .catch(console.error);

                btn.addEventListener('click', function() {
                    const channelId = this.dataset.channelId || this.dataset.userId;
                    const originalText = this.innerHTML;

                    this.disabled = true;
                    this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Обработка...';

                    fetch(`/subscribe/${channelId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            if (data.subscribed) {
                                this.classList.add('subscribed');
                                this.innerHTML = '<i class="fas fa-user-check"></i> Вы подписаны';
                            } else {
                                this.classList.remove('subscribed');
                                this.innerHTML = '<i class="fas fa-user-plus"></i> Подписаться';
                            }

                            const subscribersSpan = document.getElementById('subscribers-count-value');
                            if (subscribersSpan) {
                                subscribersSpan.textContent = data.subscribers_count;
                            }

                            window.showNotification(data.message, 'success');
                        }
                    })
                    .catch(() => window.showNotification('Ошибка при выполнении операции', 'error'))
                    .finally(() => {
                        this.disabled = false;
                    });
                });
            }
        });
    }

    // Поделиться
    function initShareButtons() {
        document.querySelectorAll('#share-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const url = window.location.href;
                navigator.clipboard.writeText(url)
                    .then(() => window.showNotification('🔗 Ссылка скопирована!', 'success'))
                    .catch(() => window.showNotification('Ошибка при копировании ссылки', 'error'));
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

        const sidebarToggle = document.querySelector('.mobile-sidebar-toggle');
        const sidebar = document.getElementById('sidebar');

        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('active');
            });
        }

        checkScreenSize();
        window.addEventListener('resize', checkScreenSize);
    }

    function checkScreenSize() {
        const isMobile = window.innerWidth <= 768;
        const mobileToggle = document.getElementById('mobile-search-toggle');
        const desktopSearch = document.querySelector('.search-bar');
        const mobileSearch = document.getElementById('mobile-search');

        if (mobileToggle) mobileToggle.style.display = isMobile ? 'flex' : 'none';
        if (desktopSearch) desktopSearch.style.display = isMobile ? 'none' : 'block';
        if (mobileSearch) mobileSearch.classList.remove('active');
    }

    // Тема
    function initTheme() {
        // Используем тему, которая уже была установлена в head
        const saved = localStorage.getItem('theme') || 'light';
        const isDark = saved === 'dark';

        // Применяем тему без анимации
        document.body.classList.toggle('dark-theme', isDark);

        // Обновляем все переключатели темы
        document.querySelectorAll('#guest-theme-toggle, .theme-toggle input[type="checkbox"]').forEach(toggle => {
            if (toggle.type === 'checkbox') {
                toggle.checked = isDark;
            }
        });

        // Убираем класс загрузки, если он еще есть
        document.documentElement.classList.remove('theme-loading');
        document.body.classList.remove('theme-loading');
    }

    // Обновленная функция переключения темы
    window.toggleTheme = function(checked) {
        const isDark = checked !== undefined ? checked : !document.body.classList.contains('dark-theme');

        // Добавляем класс загрузки на время переключения
        document.documentElement.classList.add('theme-loading');
        document.body.classList.add('theme-loading');

        // Применяем тему
        document.body.classList.toggle('dark-theme', isDark);
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        // Обновляем переключатели
        document.querySelectorAll('#guest-theme-toggle, .theme-toggle input[type="checkbox"]').forEach(toggle => {
            if (toggle.type === 'checkbox') {
                toggle.checked = isDark;
            }
        });

        // Отправляем на сервер если пользователь авторизован
        if (window.currentUser?.is_authenticated) {
            fetch('/api/theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme: isDark ? 'dark' : 'light' })
            }).catch(console.error);
        }

        // Убираем класс загрузки через небольшую задержку
        setTimeout(function() {
            document.documentElement.classList.remove('theme-loading');
            document.body.classList.remove('theme-loading');
        }, 100);
    };

    // Гостевой меню
    function initGuestMenu() {
        const settingsBtn = document.getElementById('guest-settings-btn');
        const settingsModal = document.getElementById('guest-settings-modal');
        const themeToggle = document.getElementById('guest-theme-toggle');

        if (!settingsBtn || !settingsModal) return;

        settingsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            settingsModal.classList.toggle('active');
        });

        document.addEventListener('click', (e) => {
            if (!settingsModal.contains(e.target) && !settingsBtn.contains(e.target)) {
                settingsModal.classList.remove('active');
            }
        });

        if (themeToggle) {
            themeToggle.checked = localStorage.getItem('theme') === 'dark';
            themeToggle.addEventListener('change', function() {
                window.toggleTheme(this.checked);
            });
        }
    }

    // Avatar error handler
    function initAvatarErrorHandler() {
        document.querySelectorAll('img[src*="thumbnails"]').forEach(img => {
            img.addEventListener('error', function() {
                this.src = '/uploads/thumbnails/default_avatar.png';
            });
        });
    }

    // File upload previews
    function initFileUploads() {
        const videoInput = document.getElementById('video-input');
        const uploadArea = document.getElementById('upload-area');
        const selectedFileDiv = document.getElementById('selected-file');

        if (uploadArea && videoInput) {
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');

                if (e.dataTransfer.files.length) {
                    videoInput.files = e.dataTransfer.files;
                    updateSelectedFile(e.dataTransfer.files[0], selectedFileDiv);
                }
            });

            videoInput.addEventListener('change', function() {
                if (this.files.length) {
                    updateSelectedFile(this.files[0], selectedFileDiv);
                }
            });
        }
    }

    function updateSelectedFile(file, container) {
        if (!container) return;
        container.innerHTML = `
            <div class="selected-file-info">
                <i class="fas fa-file-video"></i>
                <div>
                    <strong>${file.name}</strong>
                    <p>${(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
            </div>
        `;
    }

    // Функция для обработки скролла sidebar
    function initSidebarScroll() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    // Восстанавливаем позицию при загрузке
    const savedScrollTop = sessionStorage.getItem('sidebarScrollPosition');
    if (savedScrollTop) {
        sidebar.scrollTop = parseInt(savedScrollTop);
    }

    // Сохраняем позицию при скролле
    let scrollTimeout;
    sidebar.addEventListener('scroll', function() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function() {
            sessionStorage.setItem('sidebarScrollPosition', sidebar.scrollTop);
        }, 100);
    });

    // Сохраняем позицию перед уходом со страницы
    window.addEventListener('beforeunload', function() {
        sessionStorage.setItem('sidebarScrollPosition', sidebar.scrollTop);
    });

    // Предотвращаем всплытие события прокрутки
    sidebar.addEventListener('wheel', function(e) {
        const { scrollTop, scrollHeight, clientHeight } = this;

        // Если дошли до верха и пытаемся скроллить вверх
        if (scrollTop === 0 && e.deltaY < 0) {
            e.preventDefault();
        }

        // Если дошли до низа и пытаемся скроллить вниз
        if (scrollTop + clientHeight >= scrollHeight && e.deltaY > 0) {
            e.preventDefault();
        }

        // Останавливаем всплытие события
        e.stopPropagation();
    }, { passive: false });

    // Также обрабатываем touch-события для мобильных
    sidebar.addEventListener('touchstart', function(e) {
        this._touchStartY = e.touches[0].clientY;
        this._touchStartScrollTop = this.scrollTop;
    });

    sidebar.addEventListener('touchmove', function(e) {
        const { scrollTop, scrollHeight, clientHeight } = this;
        const touchY = e.touches[0].clientY;
        const deltaY = touchY - (this._touchStartY || touchY);

        // Если дошли до верха и пытаемся скроллить вниз
        if (scrollTop === 0 && deltaY > 0) {
            e.preventDefault();
        }

        // Если дошли до низа и пытаемся скроллить вверх
        if (scrollTop + clientHeight >= scrollHeight && deltaY < 0) {
            e.preventDefault();
        }
    }, { passive: false });
}

    // Новая функция для подсветки активных ссылок в футере
    function initActiveFooterLinks() {
        // Получаем текущий URL и endpoint
        const currentPath = window.location.pathname;

        // Словарь соответствия URL и эндпоинтов
        const endpointMap = {
            '/about': 'about_project',
            '/legal': 'legal_info',
            '/support': 'support'
        };

        // Для каждой ссылки в футере проверяем, соответствует ли она текущему пути
        document.querySelectorAll('.sidebar-footer-menu-bold a').forEach(link => {
            const href = link.getAttribute('href');

            // Проверяем прямое соответствие
            if (href === currentPath) {
                link.classList.add('active');
            }

            // Также проверяем по эндпоинтам (на случай если есть дополнительные параметры в URL)
            for (const [path, endpoint] of Object.entries(endpointMap)) {
                if (currentPath.includes(path) && href.includes(path)) {
                    link.classList.add('active');
                    break;
                }
            }
        });
    }

    // Добавляем стили для уведомлений если их нет
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();