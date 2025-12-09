/**
 * main javascript for whatsapp agent dashboard
 * handles sidebar toggle, charts, and dynamic content
 */

document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle functionality (responsive and persistent)
    const sidebarToggle = document.getElementById('sidebar-toggle') || document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');

    function isMobile() {
        return window.innerWidth < 768;
    }

    // Updates chevron direction: left for open, right for collapsed
    function setToggleIcon(open) {
        if (!sidebarToggle) return;
        sidebarToggle.innerHTML = open
            ? '<i class="fas fa-chevron-left"></i>'
            : '<i class="fas fa-chevron-right"></i>';
    }

    // Desktop: collapsed state (true/false)
    function setSidebarStateDesktop(collapsed) {
        if (!sidebar || !mainContent) return;
        if (collapsed) {
            sidebar.classList.add('collapsed');
            sidebar.classList.remove('expanded');
            mainContent.classList.add('expanded');
        } else {
            sidebar.classList.remove('collapsed');
            sidebar.classList.remove('expanded');
            mainContent.classList.remove('expanded');
        }
        setToggleIcon(!collapsed);
        localStorage.setItem('sidebar-collapsed', collapsed);
    }

    // Mobile: expanded state (true/false)
    function setSidebarStateMobile(expanded) {
        if (!sidebar || !mainContent) return;
        if (expanded) {
            sidebar.classList.add('expanded');
            sidebar.classList.remove('collapsed');
            mainContent.classList.add('expanded');
        } else {
            sidebar.classList.remove('expanded');
            sidebar.classList.remove('collapsed');
            mainContent.classList.remove('expanded');
        }
        setToggleIcon(expanded);
    }

    function getInitialCollapsed() {
        return localStorage.getItem('sidebar-collapsed') === 'true';
    }

    // On load or resize, choose the right mode for the device
    function setInitialSidebarState() {
        if (isMobile()) {
            setSidebarStateMobile(false); // Mobile starts collapsed (icons only)
        } else {
            setSidebarStateDesktop(getInitialCollapsed());
        }
    }

    // Toggle button click
    if (sidebarToggle && sidebar && mainContent) {
        sidebarToggle.addEventListener('click', function() {
            if (isMobile()) {
                const isExpanded = sidebar.classList.contains('expanded');
                setSidebarStateMobile(!isExpanded);
            } else {
                const isCollapsed = sidebar.classList.contains('collapsed');
                setSidebarStateDesktop(!isCollapsed);
            }
        });
    }

    // Handle resize (switch mode if crossing mobile/desktop breakpoint)
    window.addEventListener('resize', function() {
        setInitialSidebarState();
    });

    // Initial setup
    setInitialSidebarState();

    // Initialize other parts of the dashboard
    initializeCharts();
    initializeDatepickers();
    setupAjaxForms();
});

// initialize charts using chart.js
function initializeCharts() {
    const salesChartElement = document.getElementById('sales-chart');
    if (salesChartElement) {
        const ctx = salesChartElement.getContext('2d');
        let labels = [];
        let data = [];
        try {
            labels = JSON.parse(salesChartElement.dataset.labels || '[]');
            data = JSON.parse(salesChartElement.dataset.values || '[]');
        } catch (e) {
            console.error('Error parsing chart data', e);
        }
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Sales (R$)',
                    data: data,
                    borderColor: '#1a73e8',
                    backgroundColor: 'rgba(26, 115, 232, 0.1)',
                    borderWidth: 2,
                    pointBackgroundColor: '#1a73e8',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'R$ ' + value;
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'R$ ' + context.parsed.y;
                            }
                        }
                    }
                }
            }
        });
    }
}

// initialize datepickers
function initializeDatepickers() {
    const datepickers = document.querySelectorAll('.datepicker');
    if (datepickers.length > 0) {
        datepickers.forEach(function(element) {
            new Datepicker(element, {
                format: 'yyyy-mm-dd',
                autohide: true
            });
        });
    }
}

// setup ajax form submissions
function setupAjaxForms() {
    const ajaxForms = document.querySelectorAll('form.ajax-form');
    ajaxForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(form);
            const url = form.getAttribute('action');
            const method = form.getAttribute('method') || 'POST';
            const submitButton = form.querySelector('button[type="submit"]');
            // disable submit button and show loading
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            }
            // send ajax request
            fetch(url, {
                method: method,
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Success', data.message || 'Operation completed successfully', 'success');
                    if (data.redirect) {
                        setTimeout(function() {
                            window.location.href = data.redirect;
                        }, 1000);
                    }
                    if (data.reset_form) {
                        form.reset();
                    }
                } else {
                    showNotification('Error', data.message || 'An error occurred', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error', 'An unexpected error occurred', 'danger');
            })
            .finally(() => {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = submitButton.dataset.originalText || 'Submit';
                }
            });
        });
        // save original button text
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.dataset.originalText = submitButton.innerHTML;
        }
    });
}

// show notification
function showNotification(title, message, type) {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show notification`;
    notification.innerHTML = `
        <strong>${title}:</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    const container = document.getElementById('notifications-container') || document.body;
    container.appendChild(notification);
    setTimeout(function() {
        notification.classList.remove('show');
        setTimeout(function() {
            notification.remove();
        }, 150);
    }, 5000);
}
