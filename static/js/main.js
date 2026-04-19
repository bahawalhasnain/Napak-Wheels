// Car Marketplace JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // File upload preview
    const photoInput = document.querySelector('input[type="file"]');
    if (photoInput) {
        photoInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // Validate file size (16MB max)
                if (file.size > 16 * 1024 * 1024) {
                    alert('File size must be less than 16MB');
                    e.target.value = '';
                    return;
                }
                
                // Validate file type
                const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/jfif'];
                if (!allowedTypes.includes(file.type)) {
                    alert('Please select a valid image file (JPG, PNG, GIF, JFIF)');
                    e.target.value = '';
                    return;
                }
                
                // Show preview if it's an image
                const reader = new FileReader();
                reader.onload = function(e) {
                    // Remove existing preview
                    const existingPreview = document.querySelector('.image-preview');
                    if (existingPreview) {
                        existingPreview.remove();
                    }
                    
                    // Create new preview
                    const preview = document.createElement('div');
                    preview.className = 'image-preview mt-2';
                    preview.innerHTML = `
                        <img src="${e.target.result}" class="img-thumbnail" style="max-height: 200px;" alt="Preview">
                        <p class="text-muted mt-1">Preview of uploaded image</p>
                    `;
                    photoInput.parentNode.appendChild(preview);
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // Form validation enhancement
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Keep GET/search forms compact; avoid replacing icon button text.
            if ((form.method || '').toLowerCase() === 'get') {
                return;
            }

            // Add loading state to submit button
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
                
                // Re-enable button after 10 seconds (fallback)
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }, 10000);
            }
        });
    });

    // Price formatting
    const priceInputs = document.querySelectorAll('input[name="price"], input[name="min_price"], input[name="max_price"]');
    priceInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = parseFloat(this.value);
            if (!isNaN(value)) {
                this.value = value.toFixed(0);
            }
        });
    });

    // Phone number formatting
    const phoneInputs = document.querySelectorAll('input[name="seller_phone"]');
    phoneInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            // Remove all non-digits
            let value = e.target.value.replace(/\D/g, '');
            
            // Format as (XXX) XXX-XXXX
            if (value.length >= 6) {
                value = `(${value.slice(0, 3)}) ${value.slice(3, 6)}-${value.slice(6, 10)}`;
            } else if (value.length >= 3) {
                value = `(${value.slice(0, 3)}) ${value.slice(3)}`;
            }
            
            e.target.value = value;
        });
    });

    // Search form auto-submit with debounce
    const searchInput = document.querySelector('input[name="search"]');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                // Auto-submit search form after 1 second of no typing
                if (this.value.length >= 3 || this.value.length === 0) {
                    this.form.submit();
                }
            }, 1000);
        });
    }

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Image lazy loading
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                observer.unobserve(img);
            }
        });
    });

    images.forEach(img => imageObserver.observe(img));

    // Contact button tracking
    const contactButtons = document.querySelectorAll('a[href^="tel:"], a[href^="mailto:"]');
    contactButtons.forEach(button => {
        button.addEventListener('click', function() {
            console.log('Contact attempt:', this.href);
            // Here you could add analytics tracking
        });
    });

    // Year input validation
    const yearInputs = document.querySelectorAll('input[name="year"], input[name="min_year"], input[name="max_year"]');
    const currentYear = new Date().getFullYear();
    yearInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = parseInt(this.value);
            if (!isNaN(value)) {
                if (value < 1900) this.value = 1900;
                if (value > currentYear + 1) this.value = currentYear + 1;
            }
        });
    });

    // Mileage input validation
    const mileageInputs = document.querySelectorAll('input[name="mileage"]');
    mileageInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = parseInt(this.value);
            if (!isNaN(value) && value < 0) {
                this.value = 0;
            }
        });
    });

    // Browse cars view toggle (grid/list)
    const carResults = document.getElementById('car-results');
    const gridBtn = document.getElementById('grid-view-btn');
    const listBtn = document.getElementById('list-view-btn');
    if (carResults && gridBtn && listBtn) {
        const setView = (mode) => {
            const isList = mode === 'list';
            carResults.classList.toggle('car-results-list', isList);
            carResults.classList.toggle('car-results-grid', !isList);
            gridBtn.classList.toggle('active', !isList);
            listBtn.classList.toggle('active', isList);
            localStorage.setItem('browseCarsView', isList ? 'list' : 'grid');
        };

        gridBtn.addEventListener('click', () => setView('grid'));
        listBtn.addEventListener('click', () => setView('list'));
        setView(localStorage.getItem('browseCarsView') || 'grid');
    }
});

// Utility functions
function formatPrice(price) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(price);
}

function formatMileage(mileage) {
    return new Intl.NumberFormat('en-US').format(mileage) + ' miles';
}

// Handle browser back/forward navigation
window.addEventListener('popstate', function(e) {
    if (e.state && e.state.page) {
        // Handle state changes if needed
        console.log('Navigated to:', e.state.page);
    }
});

// Add current page to history state
history.replaceState({page: window.location.pathname}, '', window.location.href);
