/**
 * Enhanced UI Components for Fraternity Treasurer App
 * Advanced Bootstrap components and interactive elements
 */

class EnhancedUI {
    constructor() {
        this.init();
    }

    init() {
        this.initDatePickers();
        this.initMultiSelect();
        this.initCollapsibleSections();
        this.initTooltips();
        this.initFormEnhancements();
        this.initProgressBars();
        this.initLoadingButtons();
        this.initMobileEnhancements();
    }

    /**
     * Initialize enhanced date picker components
     */
    initDatePickers() {
        document.querySelectorAll('.date-picker').forEach(picker => {
            // Add calendar icon
            const wrapper = document.createElement('div');
            wrapper.className = 'date-picker-wrapper';
            
            const icon = document.createElement('i');
            icon.className = 'bi bi-calendar3 calendar-icon';
            
            picker.parentNode.insertBefore(wrapper, picker);
            wrapper.appendChild(picker);
            wrapper.appendChild(icon);

            // Set date input type
            picker.type = 'date';
            
            // Add today button functionality
            if (picker.hasAttribute('data-today-button')) {
                const todayBtn = document.createElement('button');
                todayBtn.type = 'button';
                todayBtn.className = 'btn btn-outline-secondary btn-sm mt-1';
                todayBtn.textContent = 'Today';
                todayBtn.onclick = () => {
                    picker.value = new Date().toISOString().split('T')[0];
                    picker.dispatchEvent(new Event('change'));
                };
                wrapper.appendChild(todayBtn);
            }
        });
    }

    /**
     * Initialize multi-select dropdown components
     */
    initMultiSelect() {
        document.querySelectorAll('.multi-select').forEach(select => {
            this.createMultiSelect(select);
        });
    }

    createMultiSelect(select) {
        const container = document.createElement('div');
        container.className = 'multi-select-container';

        const input = document.createElement('div');
        input.className = 'form-control multi-select-input';
        input.setAttribute('tabindex', '0');
        input.innerHTML = '<span class="placeholder">Select options...</span>';

        const dropdown = document.createElement('div');
        dropdown.className = 'multi-select-dropdown';
        dropdown.style.display = 'none';

        // Create options
        Array.from(select.options).forEach(option => {
            if (option.value) {
                const optionDiv = document.createElement('div');
                optionDiv.className = 'multi-select-option';
                optionDiv.setAttribute('data-value', option.value);
                optionDiv.innerHTML = `
                    <input type="checkbox" class="form-check-input me-2" id="ms_${option.value}">
                    <label class="form-check-label" for="ms_${option.value}">${option.text}</label>
                `;
                
                optionDiv.onclick = (e) => {
                    const checkbox = optionDiv.querySelector('input');
                    if (e.target !== checkbox) {
                        checkbox.checked = !checkbox.checked;
                    }
                    this.updateMultiSelect(select, container);
                };

                dropdown.appendChild(optionDiv);
            }
        });

        // Tags container
        const tagsContainer = document.createElement('div');
        tagsContainer.className = 'multi-select-tags';

        // Replace original select
        select.style.display = 'none';
        select.parentNode.insertBefore(container, select);
        
        container.appendChild(input);
        container.appendChild(dropdown);
        container.appendChild(tagsContainer);

        // Toggle dropdown
        input.onclick = () => {
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        };

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!container.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });

        // Store reference
        container._originalSelect = select;
    }

    updateMultiSelect(originalSelect, container) {
        const checkboxes = container.querySelectorAll('.multi-select-option input:checked');
        const tagsContainer = container.querySelector('.multi-select-tags');
        const input = container.querySelector('.multi-select-input');
        
        // Clear existing tags
        tagsContainer.innerHTML = '';
        
        // Clear original select
        Array.from(originalSelect.options).forEach(option => option.selected = false);
        
        if (checkboxes.length === 0) {
            input.innerHTML = '<span class="placeholder">Select options...</span>';
        } else {
            input.innerHTML = `<span class="text-muted">${checkboxes.length} selected</span>`;
            
            checkboxes.forEach(checkbox => {
                const value = checkbox.closest('.multi-select-option').getAttribute('data-value');
                const text = checkbox.nextElementSibling.textContent;
                
                // Select in original select
                const option = originalSelect.querySelector(`option[value="${value}"]`);
                if (option) option.selected = true;
                
                // Create tag
                const tag = document.createElement('span');
                tag.className = 'multi-select-tag';
                tag.innerHTML = `
                    ${text}
                    <span class="remove" onclick="this.parentElement.remove(); this.updateMultiSelect()">×</span>
                `;
                
                tagsContainer.appendChild(tag);
            });
        }
        
        // Dispatch change event
        originalSelect.dispatchEvent(new Event('change'));
    }

    /**
     * Initialize collapsible sections
     */
    initCollapsibleSections() {
        document.querySelectorAll('.collapsible-section').forEach(section => {
            const header = section.querySelector('.collapsible-header');
            const content = section.querySelector('.collapsible-content');
            const icon = header.querySelector('.collapsible-icon') || this.createChevronIcon();
            
            if (!header.querySelector('.collapsible-icon')) {
                header.appendChild(icon);
            }

            header.onclick = () => {
                const isExpanded = section.classList.contains('expanded');
                
                if (isExpanded) {
                    section.classList.remove('expanded');
                    content.classList.remove('show');
                } else {
                    section.classList.add('expanded');
                    content.classList.add('show');
                }
            };

            // Auto-expand if marked
            if (section.hasAttribute('data-expanded')) {
                section.classList.add('expanded');
                content.classList.add('show');
            }
        });
    }

    createChevronIcon() {
        const icon = document.createElement('i');
        icon.className = 'bi bi-chevron-down collapsible-icon';
        return icon;
    }

    /**
     * Initialize enhanced tooltips
     */
    initTooltips() {
        document.querySelectorAll('[data-tooltip]').forEach(element => {
            const tooltipText = element.getAttribute('data-tooltip');
            
            element.classList.add('tooltip-enhanced');
            
            const tooltipContent = document.createElement('div');
            tooltipContent.className = 'tooltip-content';
            tooltipContent.textContent = tooltipText;
            
            element.appendChild(tooltipContent);
        });
    }

    /**
     * Initialize form enhancements
     */
    initFormEnhancements() {
        // Floating labels
        document.querySelectorAll('.form-floating input, .form-floating select').forEach(input => {
            if (!input.placeholder) {
                input.placeholder = ' '; // Required for floating label effect
            }
        });

        // Auto-resize textareas
        document.querySelectorAll('textarea[data-auto-resize]').forEach(textarea => {
            textarea.style.overflow = 'hidden';
            
            const resize = () => {
                textarea.style.height = 'auto';
                textarea.style.height = textarea.scrollHeight + 'px';
            };
            
            textarea.addEventListener('input', resize);
            resize(); // Initial resize
        });

        // Form validation enhancements
        document.querySelectorAll('form[data-enhanced-validation]').forEach(form => {
            form.addEventListener('submit', (e) => {
                this.enhancedFormValidation(form, e);
            });
        });
    }

    enhancedFormValidation(form, event) {
        const invalidFields = form.querySelectorAll(':invalid');
        
        if (invalidFields.length > 0) {
            event.preventDefault();
            
            // Focus first invalid field
            invalidFields[0].focus();
            
            // Show custom error messages
            invalidFields.forEach(field => {
                this.showFieldError(field);
            });
        }
    }

    showFieldError(field) {
        const errorDiv = field.parentNode.querySelector('.form-error') || document.createElement('div');
        errorDiv.className = 'form-error text-danger small mt-1';
        
        if (field.validity.valueMissing) {
            errorDiv.textContent = `${field.getAttribute('data-field-name') || 'This field'} is required`;
        } else if (field.validity.typeMismatch) {
            errorDiv.textContent = 'Please enter a valid value';
        } else if (field.validity.patternMismatch) {
            errorDiv.textContent = field.getAttribute('data-error-message') || 'Invalid format';
        }
        
        if (!field.parentNode.querySelector('.form-error')) {
            field.parentNode.appendChild(errorDiv);
        }
        
        // Clear error when field becomes valid
        field.addEventListener('input', () => {
            if (field.validity.valid) {
                errorDiv.remove();
            }
        });
    }

    /**
     * Initialize progress bars with animations
     */
    initProgressBars() {
        document.querySelectorAll('.progress-enhanced').forEach(progress => {
            const progressBar = progress.querySelector('.progress-bar');
            const targetWidth = progressBar.getAttribute('aria-valuenow');
            
            // Animate progress bar
            progressBar.style.width = '0%';
            setTimeout(() => {
                progressBar.style.width = `${targetWidth}%`;
            }, 100);
            
            // Add label if specified
            if (progress.hasAttribute('data-show-label')) {
                const label = document.createElement('div');
                label.className = 'progress-label';
                label.textContent = `${targetWidth}%`;
                progress.appendChild(label);
            }
        });

        // Step progress indicators
        document.querySelectorAll('.step-progress').forEach(stepProgress => {
            const steps = stepProgress.querySelectorAll('.step-progress-item');
            const activeStep = parseInt(stepProgress.getAttribute('data-active-step') || '1');
            
            steps.forEach((step, index) => {
                const stepNumber = index + 1;
                const circle = step.querySelector('.step-progress-circle');
                
                if (stepNumber < activeStep) {
                    step.classList.add('completed');
                    circle.innerHTML = '<i class="bi bi-check"></i>';
                } else if (stepNumber === activeStep) {
                    step.classList.add('active');
                    circle.textContent = stepNumber;
                } else {
                    circle.textContent = stepNumber;
                }
            });
        });
    }

    /**
     * Initialize loading button states
     */
    initLoadingButtons() {
        document.querySelectorAll('[data-loading-button]').forEach(button => {
            button.addEventListener('click', () => {
                this.setButtonLoading(button, true);
                
                // Auto-reset after timeout if no manual reset
                const timeout = parseInt(button.getAttribute('data-loading-timeout') || '5000');
                setTimeout(() => {
                    if (button.classList.contains('btn-loading')) {
                        this.setButtonLoading(button, false);
                    }
                }, timeout);
            });
        });
    }

    setButtonLoading(button, loading) {
        if (loading) {
            button.classList.add('btn-loading');
            button.disabled = true;
            
            // Store original text
            const textElement = button.querySelector('.btn-text') || button;
            if (!button.querySelector('.btn-text')) {
                const span = document.createElement('span');
                span.className = 'btn-text';
                span.innerHTML = button.innerHTML;
                button.innerHTML = '';
                button.appendChild(span);
            }
        } else {
            button.classList.remove('btn-loading');
            button.disabled = false;
        }
    }

    /**
     * Initialize mobile-specific enhancements
     */
    initMobileEnhancements() {
        // Touch-friendly table scrolling
        document.querySelectorAll('.table-responsive').forEach(table => {
            let isScrolling = false;
            
            table.addEventListener('touchstart', () => {
                isScrolling = true;
            });
            
            table.addEventListener('touchend', () => {
                setTimeout(() => {
                    isScrolling = false;
                }, 100);
            });
            
            // Prevent accidental clicks while scrolling
            table.addEventListener('click', (e) => {
                if (isScrolling) {
                    e.preventDefault();
                }
            });
        });

        // Mobile navigation improvements
        if (window.innerWidth <= 768) {
            this.initMobileNavigation();
        }
    }

    initMobileNavigation() {
        const navbar = document.querySelector('.navbar-collapse');
        const navLinks = navbar?.querySelectorAll('.nav-link');
        
        navLinks?.forEach(link => {
            link.addEventListener('click', () => {
                // Close mobile menu after click
                const bsCollapse = new bootstrap.Collapse(navbar, {
                    hide: true
                });
            });
        });
    }

    /**
     * Utility methods for enhanced UI components
     */
    
    // Show loading skeleton
    showSkeleton(element, lines = 3) {
        const skeletonHTML = Array(lines).fill(0).map(() => 
            '<div class="skeleton" style="height: 1rem; margin-bottom: 0.5rem; border-radius: 0.25rem;"></div>'
        ).join('');
        
        element.innerHTML = skeletonHTML;
    }

    // Hide loading skeleton
    hideSkeleton(element, originalContent) {
        element.innerHTML = originalContent;
    }

    // Show notification toast
    showToast(message, type = 'info', duration = 3000) {
        const toastContainer = this.getToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0 mb-2`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: duration
        });
        
        bsToast.show();
        
        // Clean up after hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    getToastContainer() {
        let container = document.querySelector('.toast-container');
        
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1055';
            document.body.appendChild(container);
        }
        
        return container;
    }

    // Animate counter
    animateCounter(element, target, duration = 1000) {
        const start = parseInt(element.textContent) || 0;
        const increment = (target - start) / (duration / 16);
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            
            if ((increment > 0 && current >= target) || (increment < 0 && current <= target)) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = Math.round(current);
            }
        }, 16);
    }

    // Format currency
    formatCurrency(amount, showCents = true) {
        const formatter = new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: showCents ? 2 : 0,
            maximumFractionDigits: showCents ? 2 : 0
        });
        
        return formatter.format(amount);
    }

    // Debounce function calls
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Global utility functions
window.EnhancedUI = {
    // Initialize enhanced UI when DOM is loaded
    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                new EnhancedUI();
            });
        } else {
            new EnhancedUI();
        }
    },

    // Manually trigger loading state
    setLoading(button, loading) {
        const ui = new EnhancedUI();
        ui.setButtonLoading(button, loading);
    },

    // Show toast notification
    showToast(message, type, duration) {
        const ui = new EnhancedUI();
        ui.showToast(message, type, duration);
    },

    // Format currency
    formatCurrency(amount, showCents) {
        const ui = new EnhancedUI();
        return ui.formatCurrency(amount, showCents);
    }
};

// Auto-initialize on load
EnhancedUI.init();