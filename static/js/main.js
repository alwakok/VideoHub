// Основные функции JavaScript для VideoHUB
(function() {
    'use strict';

    function init() {
        initLikes();
        initComments();
        initMobileMenu();
        initTheme();
        initGuestMenu();
        initAvatarErrorHandler();
        initFileUploads();
    }

    // Лайки и избранное
    function initLikes() {
        document.querySelectorAll('.like-btn, #like-btn, .remove-favorite, #favorite-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const videoId = this.dataset.videoId || this.getAttribute('data-video-id');
                if (!videoId) return;

                const isFavorite = this.id === 'favorite-btn';
                const url = isFavorite ? `/favorite/${videoId}` : `/like/${videoId}`;

                fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
                    .then(res => res.json())
                    .then(data => {
                        this.classList.toggle('liked', data.liked || data.favorited);

                        if (isFavorite) {
                            this.innerHTML = data.favorited ?
                                '<i class="fas fa-star"></i> <span>В избранном</span>' :
                                '<i class="fas fa-star"></i> <span>В избранное</span>';
                        } else {
                            const count = this.querySelector('#like-count, .like-count');
                            if (count) count.textContent = data.like_count;
                        }
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

        // Mobile sidebar
        const sidebarToggle = document.querySelector('.mobile-sidebar-toggle');
        const sidebar = document.getElementById('sidebar');

        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('active');
            });
        }

        // User menu for mobile
        const userMenu = document.querySelector('.user-menu');
        if (userMenu && window.innerWidth <= 768) {
            userMenu.addEventListener('click', (e) => {
                e.preventDefault();
                const dropdown = userMenu.querySelector('.dropdown');
                if (dropdown) {
                    dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
                }
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

        // Синхронизация всех переключателей
        document.querySelectorAll('#guest-theme-toggle, .theme-toggle input[type="checkbox"]').forEach(toggle => {
            if (toggle.type === 'checkbox') {
                toggle.checked = isDark;
            }
        });
    }

    window.toggleTheme = function(checked) {
        const isDark = checked !== undefined ? checked : !document.body.classList.contains('dark-theme');
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

    // Notification helper
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

    // Add animation styles if not exists
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