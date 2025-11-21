// PayCrypt Theme System
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('paycrypt-theme') || 'dark';
        this.init();
    }

    init() {
        // Set initial theme
        this.setTheme(this.currentTheme);

        // Create theme switcher button
        this.createThemeSwitcher();

        // Listen for system theme changes
        this.listenForSystemTheme();
    }

    setTheme(theme) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('paycrypt-theme', theme);

        // Update theme switcher button
        this.updateThemeSwitcher();

        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: theme }
        }));
    }

    toggleTheme() {
        const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    }

    createThemeSwitcher() {
        // Create theme switcher container
        const switcher = document.createElement('div');
        switcher.id = 'theme-switcher';
        switcher.className = 'theme-switcher';
        switcher.innerHTML = `
            <button class="theme-toggle-btn" aria-label="Toggle theme">
                <i class="bi bi-moon-fill theme-icon-dark"></i>
                <i class="bi bi-sun-fill theme-icon-light"></i>
            </button>
        `;

        // Add to navbar
        const navbar = document.querySelector('.navbar-nav.ms-auto');
        if (navbar) {
            const li = document.createElement('li');
            li.className = 'nav-item';
            li.appendChild(switcher);
            navbar.insertBefore(li, navbar.firstChild);
        }

        // Add event listener
        const toggleBtn = switcher.querySelector('.theme-toggle-btn');
        toggleBtn.addEventListener('click', () => this.toggleTheme());

        this.updateThemeSwitcher();
    }

    updateThemeSwitcher() {
        const switcher = document.getElementById('theme-switcher');
        if (!switcher) return;

        const isDark = this.currentTheme === 'dark';
        switcher.classList.toggle('dark-mode', isDark);
        switcher.classList.toggle('light-mode', !isDark);
    }

    listenForSystemTheme() {
        // Listen for system theme changes if no manual preference is set
        if (!localStorage.getItem('paycrypt-theme')) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', (e) => {
                this.setTheme(e.matches ? 'dark' : 'light');
            });
        }
    }
}

// Initialize theme manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});

// Add theme switcher styles
const themeStyles = `
<style>
.theme-switcher {
    position: relative;
}

.theme-toggle-btn {
    background: var(--bg-surface);
    border: 1px solid var(--border-primary);
    border-radius: 50px;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s ease;
    color: var(--text-primary);
    position: relative;
    overflow: hidden;
}

.theme-toggle-btn:hover {
    background: var(--cyber-primary-light);
    border-color: var(--cyber-primary);
    transform: scale(1.05);
    box-shadow: var(--cyber-primary-glow);
}

.theme-icon-dark,
.theme-icon-light {
    position: absolute;
    transition: all 0.3s ease;
    font-size: 16px;
}

.theme-icon-dark {
    opacity: 1;
    transform: rotate(0deg);
}

.theme-icon-light {
    opacity: 0;
    transform: rotate(180deg);
}

.dark-mode .theme-icon-dark {
    opacity: 1;
    transform: rotate(0deg);
}

.dark-mode .theme-icon-light {
    opacity: 0;
    transform: rotate(180deg);
}

.light-mode .theme-icon-dark {
    opacity: 0;
    transform: rotate(-180deg);
}

.light-mode .theme-icon-light {
    opacity: 1;
    transform: rotate(0deg);
}

/* Smooth transitions for theme changes */
* {
    transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}

/* Reduce motion for accessibility */
@media (prefers-reduced-motion: reduce) {
    .theme-toggle-btn,
    .theme-icon-dark,
    .theme-icon-light {
        transition: none;
    }
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', themeStyles);

// Export for global use
window.ThemeManager = ThemeManager;