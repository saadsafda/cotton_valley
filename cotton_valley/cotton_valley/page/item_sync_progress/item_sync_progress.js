frappe.pages['item-sync-progress'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Item & Price Sync Progress',
        single_column: true
    });

    page.main.html(`
        <div class="container py-4">
            <!-- ITEM SYNC SECTION -->
            <h4 class="mb-3">📦 Item Sync</h4>
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Cotton Valley Items</h5>
                            <span id="cv-total-items" class="badge bg-light text-dark">0 items</span>
                        </div>
                        <div class="card-body">
                            <div id="cv-progress-container" style="display: none;">
                                <p><strong>Task ID:</strong> <span id="cv-task-id">-</span></p>
                                <p><strong>Status:</strong> <span id="cv-status" class="badge bg-info">-</span></p>
                                <p><strong>Progress:</strong> <span id="cv-current">0</span> / <span id="cv-total">0</span></p>
                                <div class="progress mb-3" style="height: 30px;">
                                    <div id="cv-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
                                         role="progressbar" style="width: 0%;">0%</div>
                                </div>
                                <p id="cv-description" class="text-muted small">-</p>
                            </div>
                            <div id="cv-no-task" class="text-center py-3">
                                <p class="text-muted">No sync in progress. Sync is managed by scheduler.</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-success text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">UDC Items</h5>
                            <span id="udc-total-items" class="badge bg-light text-dark">0 items</span>
                        </div>
                        <div class="card-body">
                            <div id="udc-progress-container" style="display: none;">
                                <p><strong>Task ID:</strong> <span id="udc-task-id">-</span></p>
                                <p><strong>Status:</strong> <span id="udc-status" class="badge bg-info">-</span></p>
                                <p><strong>Progress:</strong> <span id="udc-current">0</span> / <span id="udc-total">0</span></p>
                                <div class="progress mb-3" style="height: 30px;">
                                    <div id="udc-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated bg-success" 
                                         role="progressbar" style="width: 0%;">0%</div>
                                </div>
                                <p id="udc-description" class="text-muted small">-</p>
                            </div>
                            <div id="udc-no-task" class="text-center py-3">
                                <p class="text-muted">No sync in progress. Sync is managed by scheduler.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- PRICE SYNC SECTION -->
            <h4 class="mb-3">💰 Price Sync</h4>
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-info text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Cotton Valley Prices</h5>
                            <span id="cv-price-total-items" class="badge bg-light text-dark">0 items</span>
                        </div>
                        <div class="card-body">
                            <div id="cv-price-progress-container" style="display: none;">
                                <p><strong>Task ID:</strong> <span id="cv-price-task-id">-</span></p>
                                <p><strong>Status:</strong> <span id="cv-price-status" class="badge bg-info">-</span></p>
                                <p><strong>Progress:</strong> <span id="cv-price-current">0</span> / <span id="cv-price-total">0</span></p>
                                <div class="progress mb-3" style="height: 30px;">
                                    <div id="cv-price-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated bg-info" 
                                         role="progressbar" style="width: 0%;">0%</div>
                                </div>
                                <p id="cv-price-description" class="text-muted small">-</p>
                            </div>
                            <div id="cv-price-no-task" class="text-center py-3">
                                <p class="text-muted">No price sync in progress. Sync is managed by scheduler.</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-warning text-dark d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">UDC Prices</h5>
                            <span id="udc-price-total-items" class="badge bg-light text-dark">0 items</span>
                        </div>
                        <div class="card-body">
                            <div id="udc-price-progress-container" style="display: none;">
                                <p><strong>Task ID:</strong> <span id="udc-price-task-id">-</span></p>
                                <p><strong>Status:</strong> <span id="udc-price-status" class="badge bg-info">-</span></p>
                                <p><strong>Progress:</strong> <span id="udc-price-current">0</span> / <span id="udc-price-total">0</span></p>
                                <div class="progress mb-3" style="height: 30px;">
                                    <div id="udc-price-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated bg-warning" 
                                         role="progressbar" style="width: 0%;">0%</div>
                                </div>
                                <p id="udc-price-description" class="text-muted small">-</p>
                            </div>
                            <div id="udc-price-no-task" class="text-center py-3">
                                <p class="text-muted">No price sync in progress. Sync is managed by scheduler.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">Sync Activity Log</h5>
                    <button id="clear-log" class="btn btn-sm btn-outline-secondary">Clear Log</button>
                </div>
                <div class="card-body">
                    <div id="sync-log" style="max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px; background: #f8f9fa; padding: 10px; border-radius: 5px;">
                        <p class="text-muted">Logs will appear here...</p>
                    </div>
                </div>
            </div>
        </div>
        
        <style>
            .progress {
                border-radius: 10px;
                background-color: #e9ecef;
            }
            .progress-bar {
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
                line-height: 30px;
            }
            .card {
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border: none;
            }
            .card-header {
                border-bottom: none;
            }
            #sync-log p {
                margin: 2px 0;
                padding: 4px 8px;
                border-left: 3px solid #dee2e6;
            }
            #sync-log p.log-info { border-left-color: #0dcaf0; }
            #sync-log p.log-success { border-left-color: #198754; }
            #sync-log p.log-error { border-left-color: #dc3545; }
            #sync-log p.log-warning { border-left-color: #ffc107; }
        </style>
    `);

    let cvTaskId = null;
    let udcTaskId = null;
    let cvPriceTaskId = null;
    let udcPriceTaskId = null;

    function addLog(message, type = 'info') {
        const logDiv = document.getElementById('sync-log');
        const timestamp = new Date().toLocaleTimeString();
        const firstP = logDiv.querySelector('p.text-muted');
        if (firstP && firstP.textContent.includes('Logs will appear')) {
            firstP.remove();
        }
        const p = document.createElement('p');
        p.className = `log-${type}`;
        p.innerHTML = `<span class="text-muted">[${timestamp}]</span> ${message}`;
        logDiv.insertBefore(p, logDiv.firstChild);
    }

    // Get item counts
    frappe.call({
        method: 'frappe.client.get_count',
        args: { doctype: 'Item', filters: { company: 'Cotton Valley' } },
        callback: function(r) {
            if (r.message) {
                document.getElementById('cv-total-items').textContent = r.message + ' items';
                document.getElementById('cv-price-total-items').textContent = r.message + ' items';
            }
        }
    });

    frappe.call({
        method: 'frappe.client.get_count',
        args: { doctype: 'Item', filters: { company: 'UDC' } },
        callback: function(r) {
            if (r.message) {
                document.getElementById('udc-total-items').textContent = r.message + ' items';
                document.getElementById('udc-price-total-items').textContent = r.message + ' items';
            }
        }
    });

    // Listen for custom progress updates via realtime
    frappe.realtime.on('item_sync_progress', function(data) {
        console.log('Received progress:', data);
        
        // Build log message with batch info if scheduler run
        let batchInfo = '';
        if (data.batch_number && data.total_batches) {
            batchInfo = ` [Batch ${data.batch_number}/${data.total_batches}]`;
        }
        addLog(`${data.company}${batchInfo}: ${data.item_code || 'finishing'} (${data.current}/${data.total}) - ${data.percent}%`, 'info');
        
        // CV Progress
        if (data.company === 'Cotton Valley') {
            document.getElementById('cv-progress-container').style.display = 'block';
            document.getElementById('cv-no-task').style.display = 'none';
            document.getElementById('cv-task-id').textContent = data.task_id;
            document.getElementById('cv-progress-bar').style.width = data.percent + '%';
            document.getElementById('cv-progress-bar').textContent = data.percent + '%';
            document.getElementById('cv-current').textContent = data.current;
            document.getElementById('cv-total').textContent = data.total;
            
            // Build description with batch info
            let description = data.item_code ? `Processing: ${data.item_code}` : '';
            if (data.batch_number && data.total_batches) {
                description += ` (Batch ${data.batch_number} of ${data.total_batches})`;
            }
            document.getElementById('cv-description').textContent = description;
            
            if (data.status === 'complete') {
                document.getElementById('cv-status').textContent = 'Complete';
                document.getElementById('cv-status').className = 'badge bg-success';
                document.getElementById('cv-progress-bar').classList.remove('progress-bar-animated');
                document.getElementById('cv-description').textContent = `Done! Processed: ${data.processed}, Errors: ${data.error_count}`;
                addLog(`CV Sync completed! Processed: ${data.processed}, Errors: ${data.error_count}`, 'success');
                cvTaskId = null;
            } else if (data.status === 'batch_complete') {
                // Batch completed but more batches to process
                document.getElementById('cv-status').textContent = `Batch ${data.batch_number}/${data.total_batches}`;
                document.getElementById('cv-status').className = 'badge bg-info';
                addLog(`CV Batch ${data.batch_number}/${data.total_batches} completed. Processed: ${data.processed}, Errors: ${data.error_count}`, 'info');
            } else {
                let statusText = 'Running';
                if (data.batch_number && data.total_batches) {
                    statusText = `Batch ${data.batch_number}/${data.total_batches}`;
                }
                document.getElementById('cv-status').textContent = statusText;
                document.getElementById('cv-status').className = 'badge bg-warning';
            }
        }
        
        // UDC Progress
        if (data.company === 'UDC') {
            document.getElementById('udc-progress-container').style.display = 'block';
            document.getElementById('udc-no-task').style.display = 'none';
            document.getElementById('udc-task-id').textContent = data.task_id;
            document.getElementById('udc-progress-bar').style.width = data.percent + '%';
            document.getElementById('udc-progress-bar').textContent = data.percent + '%';
            document.getElementById('udc-current').textContent = data.current;
            document.getElementById('udc-total').textContent = data.total;
            
            // Build description with batch info
            let description = data.item_code ? `Processing: ${data.item_code}` : '';
            if (data.batch_number && data.total_batches) {
                description += ` (Batch ${data.batch_number} of ${data.total_batches})`;
            }
            document.getElementById('udc-description').textContent = description;
            
            if (data.status === 'complete') {
                document.getElementById('udc-status').textContent = 'Complete';
                document.getElementById('udc-status').className = 'badge bg-success';
                document.getElementById('udc-progress-bar').classList.remove('progress-bar-animated');
                document.getElementById('udc-description').textContent = `Done! Processed: ${data.processed}, Errors: ${data.error_count}`;
                addLog(`UDC Sync completed! Processed: ${data.processed}, Errors: ${data.error_count}`, 'success');
                udcTaskId = null;
            } else if (data.status === 'batch_complete') {
                // Batch completed but more batches to process
                document.getElementById('udc-status').textContent = `Batch ${data.batch_number}/${data.total_batches}`;
                document.getElementById('udc-status').className = 'badge bg-info';
                addLog(`UDC Batch ${data.batch_number}/${data.total_batches} completed. Processed: ${data.processed}, Errors: ${data.error_count}`, 'info');
            } else {
                let statusText = 'Running';
                if (data.batch_number && data.total_batches) {
                    statusText = `Batch ${data.batch_number}/${data.total_batches}`;
                }
                document.getElementById('udc-status').textContent = statusText;
                document.getElementById('udc-status').className = 'badge bg-warning';
            }
        }
    });

    // Clear log button
    document.getElementById('clear-log').addEventListener('click', function() {
        document.getElementById('sync-log').innerHTML = '<p class="text-muted">Logs cleared...</p>';
    });

    // Listen for price sync progress updates
    frappe.realtime.on('price_sync_progress', function(data) {
        console.log('Received price progress:', data);
        
        let batchInfo = '';
        if (data.batch_number && data.total_batches) {
            batchInfo = ` [Batch ${data.batch_number}/${data.total_batches}]`;
        }
        addLog(`💰 ${data.company} Price${batchInfo}: ${data.item_code || 'finishing'} (${data.current}/${data.total}) - ${data.percent}%`, 'info');
        
        // CV Price Progress
        if (data.company === 'Cotton Valley') {
            document.getElementById('cv-price-progress-container').style.display = 'block';
            document.getElementById('cv-price-no-task').style.display = 'none';
            document.getElementById('cv-price-task-id').textContent = data.task_id;
            document.getElementById('cv-price-progress-bar').style.width = data.percent + '%';
            document.getElementById('cv-price-progress-bar').textContent = data.percent + '%';
            document.getElementById('cv-price-current').textContent = data.current;
            document.getElementById('cv-price-total').textContent = data.total;
            
            let description = data.item_code ? `Processing: ${data.item_code}` : '';
            if (data.batch_number && data.total_batches) {
                description += ` (Batch ${data.batch_number} of ${data.total_batches})`;
            }
            document.getElementById('cv-price-description').textContent = description;
            
            if (data.status === 'complete') {
                document.getElementById('cv-price-status').textContent = 'Complete';
                document.getElementById('cv-price-status').className = 'badge bg-success';
                document.getElementById('cv-price-progress-bar').classList.remove('progress-bar-animated');
                document.getElementById('cv-price-description').textContent = `Done! Processed: ${data.processed}, Errors: ${data.error_count}`;
                addLog(`💰 CV Price Sync completed! Processed: ${data.processed}, Errors: ${data.error_count}`, 'success');
                cvPriceTaskId = null;
            } else if (data.status === 'batch_complete') {
                document.getElementById('cv-price-status').textContent = `Batch ${data.batch_number}/${data.total_batches}`;
                document.getElementById('cv-price-status').className = 'badge bg-info';
                addLog(`💰 CV Price Batch ${data.batch_number}/${data.total_batches} completed. Processed: ${data.processed}, Errors: ${data.error_count}`, 'info');
            } else {
                let statusText = 'Running';
                if (data.batch_number && data.total_batches) {
                    statusText = `Batch ${data.batch_number}/${data.total_batches}`;
                }
                document.getElementById('cv-price-status').textContent = statusText;
                document.getElementById('cv-price-status').className = 'badge bg-warning';
            }
        }
        
        // UDC Price Progress
        if (data.company === 'UDC') {
            document.getElementById('udc-price-progress-container').style.display = 'block';
            document.getElementById('udc-price-no-task').style.display = 'none';
            document.getElementById('udc-price-task-id').textContent = data.task_id;
            document.getElementById('udc-price-progress-bar').style.width = data.percent + '%';
            document.getElementById('udc-price-progress-bar').textContent = data.percent + '%';
            document.getElementById('udc-price-current').textContent = data.current;
            document.getElementById('udc-price-total').textContent = data.total;
            
            let description = data.item_code ? `Processing: ${data.item_code}` : '';
            if (data.batch_number && data.total_batches) {
                description += ` (Batch ${data.batch_number} of ${data.total_batches})`;
            }
            document.getElementById('udc-price-description').textContent = description;
            
            if (data.status === 'complete') {
                document.getElementById('udc-price-status').textContent = 'Complete';
                document.getElementById('udc-price-status').className = 'badge bg-success';
                document.getElementById('udc-price-progress-bar').classList.remove('progress-bar-animated');
                document.getElementById('udc-price-description').textContent = `Done! Processed: ${data.processed}, Errors: ${data.error_count}`;
                addLog(`💰 UDC Price Sync completed! Processed: ${data.processed}, Errors: ${data.error_count}`, 'success');
                udcPriceTaskId = null;
            } else if (data.status === 'batch_complete') {
                document.getElementById('udc-price-status').textContent = `Batch ${data.batch_number}/${data.total_batches}`;
                document.getElementById('udc-price-status').className = 'badge bg-info';
                addLog(`💰 UDC Price Batch ${data.batch_number}/${data.total_batches} completed. Processed: ${data.processed}, Errors: ${data.error_count}`, 'info');
            } else {
                let statusText = 'Running';
                if (data.batch_number && data.total_batches) {
                    statusText = `Batch ${data.batch_number}/${data.total_batches}`;
                }
                document.getElementById('udc-price-status').textContent = statusText;
                document.getElementById('udc-price-status').className = 'badge bg-warning';
            }
        }
    });

    addLog('Page loaded. Sync is managed by scheduler.', 'info');
};
