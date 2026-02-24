/**
 * Auto-refresh functionality for Modem Batch Upgrade Operations
 * UI-005: Provide auto-refresh and manual refresh button
 */
(function() {
    'use strict';
    
    // Only run on batch operation detail pages
    if (!window.location.pathname.includes('/modembatchupgradeoperation/')) {
        return;
    }
    
    /**
     * Add a manual refresh button to the page
     */
    const addRefreshButton = () => {
        const objectTools = document.querySelector('.object-tools');
        if (objectTools && !document.querySelector('#refresh-status-btn')) {
            const li = document.createElement('li');
            li.innerHTML = `
                <a href="#" id="refresh-status-btn" class="historylink" title="Refresh operation status">
                    <svg style="width: 16px; height: 16px; vertical-align: middle; margin-right: 4px;" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                    </svg>
                    Refresh Status
                </a>
            `;
            objectTools.insertBefore(li, objectTools.firstChild);
            
            document.getElementById('refresh-status-btn').addEventListener('click', (e) => {
                e.preventDefault();
                
                // Show loading indicator
                const btn = e.currentTarget;
                const originalText = btn.innerHTML;
                btn.innerHTML = '↻ Refreshing...';
                btn.style.opacity = '0.5';
                btn.style.pointerEvents = 'none';
                
                // Reload after short delay for visual feedback
                setTimeout(() => {
                    location.reload();
                }, 300);
            });
        }
    };
    
    /**
     * Auto-refresh if operation is in progress
     */
    const autoRefresh = () => {
        // Check if status field exists and indicates in-progress
        const statusField = document.querySelector('.field-status .readonly');
        
        if (statusField) {
            const statusText = statusField.textContent.trim().toLowerCase();
            
            if (statusText === 'in progress' || statusText === 'in-progress') {
                // Show countdown indicator
                addCountdownIndicator();
                
                // Auto-refresh after 10 seconds
                setTimeout(() => {
                    console.log('Auto-refreshing due to in-progress status...');
                    location.reload();
                }, 10000); // 10 seconds
            }
        }
    };
    
    /**
     * Add a visual countdown indicator
     */
    const addCountdownIndicator = () => {
        const statusField = document.querySelector('.field-status');
        if (statusField && !document.querySelector('#auto-refresh-indicator')) {
            const indicator = document.createElement('div');
            indicator.id = 'auto-refresh-indicator';
            indicator.style.cssText = `
                display: inline-block;
                margin-left: 10px;
                padding: 4px 8px;
                background: #e8f4f8;
                border: 1px solid #b3d9e6;
                border-radius: 3px;
                font-size: 12px;
                color: #0c4b67;
            `;
            indicator.innerHTML = '↻ Auto-refreshing in <span id="countdown">10</span>s';
            
            statusField.appendChild(indicator);
            
            // Start countdown
            let seconds = 10;
            const countdownEl = document.getElementById('countdown');
            const interval = setInterval(() => {
                seconds--;
                if (countdownEl) {
                    countdownEl.textContent = seconds;
                }
                if (seconds <= 0) {
                    clearInterval(interval);
                }
            }, 1000);
        }
    };
    
    /**
     * Update the info banner text to reflect auto-refresh capability
     */
    const updateInfoBanner = () => {
        const messagelist = document.querySelectorAll('.messagelist li.info');
        messagelist.forEach(msg => {
            const text = msg.textContent;
            if (text.includes('Refresh the page from time to time')) {
                msg.innerHTML = msg.innerHTML.replace(
                    'Refresh the page from time to time to check its progress.',
                    'The page will auto-refresh every 10 seconds while the operation is in progress. You can also use the "Refresh Status" button above.'
                );
            }
        });
    };
    
    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        addRefreshButton();
        autoRefresh();
        updateInfoBanner();
    });
})();
