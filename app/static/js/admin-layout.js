// Sidebar Toggle Functionality
const sidebarToggleLayout = document.getElementById('sidebarToggle');
if (sidebarToggleLayout) {
    sidebarToggleLayout.addEventListener('click', (e) => {
        e.preventDefault();
        document.body.classList.toggle('sb-sidenav-toggled');
    });
}

// Add active class to current page link
const currentPage = window.location.pathname;
const navLinks = document.querySelectorAll('.nav-link');

navLinks.forEach(link => {
    if (link.href === window.location.href) {
        link.classList.add('active');
    }
});

// Fix for sidebar navigation links - ensure they are clickable
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap collapse components manually (in case they're not auto-initialized)
    const collapseElements = document.querySelectorAll('.collapse');
    collapseElements.forEach(element => {
        if (typeof bootstrap !== 'undefined' && bootstrap.Collapse) {
            // Don't initialize if already initialized
            if (!bootstrap.Collapse.getInstance(element)) {
                new bootstrap.Collapse(element, {
                    toggle: false // Don't auto-toggle on initialization
                });
            }
        }
    });

    // For non-toggle links, allow normal navigation
    const sidebarNavLinks = document.querySelectorAll('.sb-sidenav-menu .nav-link:not([data-bs-toggle])');
    
    sidebarNavLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Allow normal navigation for non-toggle links - no special handling needed
            // The browser will handle the navigation naturally
        });
    });
    
    // Handle collapse toggle links separately - let Bootstrap handle them
    const collapseToggles = document.querySelectorAll('.sb-sidenav-menu .nav-link[data-bs-toggle="collapse"]');
    collapseToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            // Don't prevent default - let Bootstrap handle the collapse
            // The data-bs-toggle and data-bs-target attributes will handle the rest
        });
    });
});

// Automatically collapse sidebar menu sections on mobile
if (window.innerWidth < 992) {
    // Collapse all expanded sections
    document.querySelectorAll('.collapse.show').forEach(function(el) {
        el.classList.remove('show');
    });
    
    // Add event listener for window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth < 992) {
            document.querySelectorAll('.collapse.show').forEach(function(el) {
                el.classList.remove('show');
            });
        }
    });
}

// Handle scroll to top button
const scrollToTopBtn = document.createElement('button');
scrollToTopBtn.className = 'scroll-to-top rounded';
scrollToTopBtn.innerHTML = '<i class="fas fa-arrow-up"></i>';
scrollToTopBtn.style.cssText = `
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    z-index: 1040;
    display: none;
    width: 40px;
    height: 40px;
    background-color: var(--primary);
    color: white;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    transition: var(--transition-base);
`;

scrollToTopBtn.addEventListener('click', () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

document.body.appendChild(scrollToTopBtn);

// Show/hide scroll to top button based on scroll position
window.addEventListener('scroll', () => {
    if (window.scrollY > 100) {
        scrollToTopBtn.style.display = 'block';
    } else {
        scrollToTopBtn.style.display = 'none';
    }
});

// Add hover effect to scroll to top button
scrollToTopBtn.addEventListener('mouseenter', () => {
    scrollToTopBtn.style.transform = 'scale(1.1)';
});

scrollToTopBtn.addEventListener('mouseleave', () => {
    scrollToTopBtn.style.transform = 'scale(1)';
});

// Initialize tooltips
const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});
