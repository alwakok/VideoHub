// Основные функции JavaScript для VideoHUB

(function() {
    'use strict';

    let isSubmitting = false;
    let notificationTimeout = null;

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
        initActiveFooterLinks();
        initFlashMessages();
    }

    // Функция для показа уведомлений (автоматически исчезают через 3 секунды)
    window.showNotification = function(message, type = 'info') {
        const colors = {
            success: '#5CB85C',
            error: '#D9534F',
            info: '#B380E6',
            warning: '#FFA500'
        };

        // Удаляем предыдущее уведомление, если оно есть
        const oldNotification = document.querySelector('.notification');
        if (oldNotification) {
            if (notificationTimeout) {
                clearTimeout(notificationTimeout);
            }
            oldNotification.remove();
        }

        // Создаем новое уведомление
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            background: ${colors[type] || colors.info};
            color: white;
            border-radius: 8px;
            z-index: 9999;
            animation: slideIn 0.3s ease forwards;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-size: 14px;
            font-weight: 500;
            max-width: 350px;
            pointer-events: none;
        `;

        document.body.appendChild(notification);

        // Устанавливаем таймер на удаление через 3 секунды
        notificationTimeout = setTimeout(() => {
            removeNotification(notification);
        }, 3000);
    };

    // Функция для удаления уведомления с анимацией
    function removeNotification(notification) {
        if (notification && notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => {
                if (notification && notification.parentNode) {
                    notification.remove();
                }
                notificationTimeout = null;
            }, 300);
        }
    }

    // Функция для обработки flash-сообщений (автоматическое исчезновение)
    function initFlashMessages() {
        const flashMessages = document.querySelectorAll('.flash');

        flashMessages.forEach((flash, index) => {
            const message = flash.textContent;
            let type = 'info';

            if (flash.classList.contains('flash-success')) {
                type = 'success';
            } else if (flash.classList.contains('flash-error')) {
                type = 'error';
            }

            flash.remove();

            setTimeout(() => {
                window.showNotification(message, type);
            }, index * 500);
        });
    }


    // Функция для обновления счетчика избранного в сайдбаре
    function updateFavoriteBadge(count) {
        // Ищем ссылку на избранное в сайдбаре
        const favoriteLinks = document.querySelectorAll('.sidebar-menu a[href*="playlist"][href*="Избранное"], .sidebar-menu a[href*="favorites"]');

        favoriteLinks.forEach(link => {
            let badge = link.querySelector('.badge');

            if (count > 0) {
                if (badge) {
                    badge.textContent = count;
                } else {
                    badge = document.createElement('span');
                    badge.className = 'badge';
                    badge.textContent = count;
                    link.appendChild(badge);
                }
            } else {
                if (badge) {
                    badge.remove();
                }
            }
        });
    }

    // Комментарии
    function initComments() {
        const form = document.getElementById('comment-form');
        if (!form) return;

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
                        <a href="/profile/${comment.author.username}" class="comment-author">${escapeHtml(comment.author.username)}</a>
                        <span class="comment-date">${escapeHtml(comment.created_at)}</span>
                    </div>
                    <p class="comment-text">${escapeHtml(comment.content)}</p>
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
        const saved = localStorage.getItem('theme') || 'light';
        const isDark = saved === 'dark';

        document.body.classList.toggle('dark-theme', isDark);

        document.querySelectorAll('#guest-theme-toggle, .theme-toggle input[type="checkbox"]').forEach(toggle => {
            if (toggle.type === 'checkbox') {
                toggle.checked = isDark;
            }
        });

        document.documentElement.classList.remove('theme-loading');
        document.body.classList.remove('theme-loading');
    }

    window.toggleTheme = function(checked) {
        const isDark = checked !== undefined ? checked : !document.body.classList.contains('dark-theme');

        document.documentElement.classList.add('theme-loading');
        document.body.classList.add('theme-loading');

        document.body.classList.toggle('dark-theme', isDark);
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        document.querySelectorAll('#guest-theme-toggle, .theme-toggle input[type="checkbox"]').forEach(toggle => {
            if (toggle.type === 'checkbox') {
                toggle.checked = isDark;
            }
        });

        if (window.currentUser?.is_authenticated) {
            fetch('/api/theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme: isDark ? 'dark' : 'light' })
            }).catch(console.error);
        }

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
                    <strong>${escapeHtml(file.name)}</strong>
                    <p>${(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
            </div>
        `;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Функция для обработки скролла sidebar
    function initSidebarScroll() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;

        const savedScrollTop = sessionStorage.getItem('sidebarScrollPosition');
        if (savedScrollTop) {
            sidebar.scrollTop = parseInt(savedScrollTop);
        }

        let scrollTimeout;
        sidebar.addEventListener('scroll', function() {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(function() {
                sessionStorage.setItem('sidebarScrollPosition', sidebar.scrollTop);
            }, 100);
        });

        window.addEventListener('beforeunload', function() {
            sessionStorage.setItem('sidebarScrollPosition', sidebar.scrollTop);
        });

        sidebar.addEventListener('wheel', function(e) {
            const { scrollTop, scrollHeight, clientHeight } = this;

            if (scrollTop === 0 && e.deltaY < 0) {
                e.preventDefault();
            }

            if (scrollTop + clientHeight >= scrollHeight && e.deltaY > 0) {
                e.preventDefault();
            }

            e.stopPropagation();
        }, { passive: false });

        sidebar.addEventListener('touchstart', function(e) {
            this._touchStartY = e.touches[0].clientY;
            this._touchStartScrollTop = this.scrollTop;
        });

        sidebar.addEventListener('touchmove', function(e) {
            const { scrollTop, scrollHeight, clientHeight } = this;
            const touchY = e.touches[0].clientY;
            const deltaY = touchY - (this._touchStartY || touchY);

            if (scrollTop === 0 && deltaY > 0) {
                e.preventDefault();
            }

            if (scrollTop + clientHeight >= scrollHeight && deltaY < 0) {
                e.preventDefault();
            }
        }, { passive: false });
    }

    // Функция для подсветки активных ссылок в футере
    function initActiveFooterLinks() {
        const currentPath = window.location.pathname;

        const endpointMap = {
            '/about': 'about_project',
            '/legal': 'legal_info',
            '/support': 'support'
        };

        document.querySelectorAll('.sidebar-footer-menu-bold a').forEach(link => {
            const href = link.getAttribute('href');

            if (href === currentPath) {
                link.classList.add('active');
            }

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
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();