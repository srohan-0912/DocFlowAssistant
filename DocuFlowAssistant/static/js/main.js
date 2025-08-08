// Global variables
let currentDocumentId = null;
let typeChart = null;

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const processingSection = document.getElementById('processingSection');
const resultsSection = document.getElementById('resultsSection');
const errorSection = document.getElementById('errorSection');

// Initialize event listeners
document.addEventListener('DOMContentLoaded', function() {
    initializeUpload();
    initializeReclassification();
});

function initializeUpload() {
    if (!uploadArea || !fileInput || !browseBtn) return;

    // File input change event
    fileInput.addEventListener('change', handleFileSelect);

    // Browse button click - make sure it triggers file input
    browseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
    });

    // Also handle clicks on the upload area itself
    uploadArea.addEventListener('click', (e) => {
        // Only trigger if not clicking the browse button directly
        if (e.target !== browseBtn && !browseBtn.contains(e.target)) {
            fileInput.click();
        }
    });

    // Drag and drop events
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);

    // Process another button
    const processAnotherBtn = document.getElementById('processAnotherBtn');
    if (processAnotherBtn) {
        processAnotherBtn.addEventListener('click', resetUploadForm);
    }

    // Retry button
    const retryBtn = document.getElementById('retryBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', resetUploadForm);
    }
}

function initializeReclassification() {
    const manualClassification = document.getElementById('manualClassification');
    const reclassifyBtn = document.getElementById('reclassifyBtn');

    if (manualClassification) {
        manualClassification.addEventListener('change', function() {
            if (this.value && reclassifyBtn) {
                reclassifyBtn.style.display = 'inline-block';
            } else if (reclassifyBtn) {
                reclassifyBtn.style.display = 'none';
            }
        });
    }

    if (reclassifyBtn) {
        reclassifyBtn.addEventListener('click', handleManualReclassification);
    }
}

// Drag and drop handlers
function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

function handleFile(file) {
    // Validate file type
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'image/jpeg', 'image/jpg', 'image/png'];
    if (!allowedTypes.includes(file.type)) {
        showError('Invalid file type. Please upload PDF, DOCX, JPG, or PNG files.');
        return;
    }

    // Validate file size (16MB limit)
    if (file.size > 16 * 1024 * 1024) {
        showError('File too large. Maximum size is 16MB.');
        return;
    }

    uploadFile(file);
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    // Show processing section
    hideAllSections();
    processingSection.style.display = 'block';
    updateProgress(10, 'Uploading file...');

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentDocumentId = data.document_id;
            updateProgress(30, 'File uploaded successfully. Starting processing...');
            processDocument(currentDocumentId);
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    })
    .catch(error => {
        console.error('Upload error:', error);
        showError('Upload failed: ' + error.message);
    });
}

// function processDocument(documentId, event = null) {
//     if (!documentId) {
//         showError('No document ID provided');
//         return;
//     }

//     // Show spinner on clicked button
//     if (event) {
//         const button = event.target.closest('button');
//         button.disabled = true;
//         button.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>Processing...`;
//     }

//     // Show progress bar
//     updateProgress(30, 'Retrying document...');

//     fetch(`/process/${documentId}`, {
//         method: 'POST'
//     })
//     .then(response => response.json())
//     .then(data => {
//         if (data.success) {
//             updateProgress(70, 'Classifying document...');

//             setTimeout(() => {
//                 updateProgress(100, 'Document successfully processed and classified!');
                
//                 // Option 1: Reload the page to reflect updated classification
//                 // location.reload();

//                 // Option 2 (Advanced): Call showResults(data) and update only the row
//                 showResults(data);

//             }, 1000);
//         } else {
//             throw new Error(data.error || 'Retry failed');
//         }
//     })
//     .catch(error => {
//         console.error('Error during retry:', error);
//         showError('Retry failed: ' + error.message);
//     });
// }

function processDocument(documentId) {
    if (!documentId) {
        showError('No document ID provided');
        return;
    }
    // Show spinner on clicked button
    if (event) {
        const button = event.target.closest('button');
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>Processing...`;
    }

    updateProgress(50, 'Extracting text using OCR...');

    fetch(`/process/${documentId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateProgress(80, 'Classifying document...');
            setTimeout(() => {
                updateProgress(100, 'Processing complete!');
                showResults(data);  // 🔥 this is what was missing
            }, 1000);
        } else {
            throw new Error(data.error || 'Processing failed');
        }
    })
    .catch(error => {
        console.error('Processing error:', error);
        showError('Processing failed: ' + error.message);
    });
}

function showResults(data) {
    hideAllSections();
    resultsSection.style.display = 'block';

    console.log("Classification response:", data); // Debugging line

    // Safely access nested values with fallback
    const docType = data?.classification?.type || 'Not classified';
    const confidence = data?.classification?.confidence ?? 0;
    const routedTo = data?.routing?.department || 'Unassigned';

    document.getElementById('documentType').textContent = docType;
    document.getElementById('confidence').innerHTML = `
        <span class="badge bg-${getConfidenceBadgeClass(confidence)}">
            ${Math.round(confidence * 100)}%
        </span>
    `;
    document.getElementById('routedTo').textContent = routedTo;

    // Update extracted text preview
    const extractedTextDiv = document.getElementById('extractedText');
    extractedTextDiv.innerHTML = `<pre class="text-wrap">${data.extracted_text || '[No text extracted]'}</pre>`;

    // Reset manual classification
    const manualClassification = document.getElementById('manualClassification');
    const reclassifyBtn = document.getElementById('reclassifyBtn');
    if (manualClassification) manualClassification.value = '';
    if (reclassifyBtn) reclassifyBtn.style.display = 'none';
}

function handleManualReclassification() {
    const newType = document.getElementById('manualClassification').value;
    if (!newType || !currentDocumentId) return;

    fetch(`/reclassify/${currentDocumentId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ new_type: newType })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update display with new classification
            document.getElementById('documentType').textContent = data.document.document_type;
            document.getElementById('confidence').innerHTML = `
                <span class="badge bg-success">100%</span> <small class="text-muted">(Manual)</small>
            `;
            document.getElementById('routedTo').textContent = data.routing.department;

            // Hide reclassify button
            document.getElementById('reclassifyBtn').style.display = 'none';
            document.getElementById('manualClassification').value = '';

            showAlert('Document reclassified successfully!', 'success');
        } else {
            throw new Error(data.error || 'Reclassification failed');
        }
    })
    .catch(error => {
        console.error('Reclassification error:', error);
        showAlert('Reclassification failed: ' + error.message, 'danger');
    });
}

function getConfidenceBadgeClass(confidence) {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'danger';
}

function updateProgress(percent, message) {
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('processingStatus');
    const container = document.getElementById('progressContainer');

    if (progressBar) {
        progressBar.style.width = percent + '%';
    }
    if (statusText) {
        statusText.textContent = message;
    }
    if (container) {
        container.style.display = 'block';
    }
}


function hideAllSections() {
    if (processingSection) processingSection.style.display = 'none';
    if (resultsSection) resultsSection.style.display = 'none';
    if (errorSection) errorSection.style.display = 'none';
}

function showError(message) {
    hideAllSections();
    if (errorSection) {
        errorSection.style.display = 'block';
        const errorMessage = document.getElementById('errorMessage');
        if (errorMessage) {
            errorMessage.textContent = message;
        }
    }
}

function resetUploadForm() {
    hideAllSections();
    if (fileInput) fileInput.value = '';
    currentDocumentId = null;

    // Show upload area
    const uploadSection = document.querySelector('.upload-section');
    if (uploadSection) {
        uploadSection.style.display = 'block';
    }
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    // Insert at top of container
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Pipeline Demo functions
function loadPipelineDemo() {
    const demoDiv = document.getElementById('pipelineDemo');
    const loadingDiv = document.getElementById('pipelineLoading');

    // Show loading, hide demo
    demoDiv.style.display = 'none';
    loadingDiv.style.display = 'block';

    fetch('/api/pipeline-demo')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayPipelineResults(data);
                demoDiv.style.display = 'block';
            } else {
                showMessage('Error running pipeline demo: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Pipeline demo error:', error);
            showAlert('Error running pipeline demo', 'danger');
        })
        .finally(() => {
            loadingDiv.style.display = 'none';
        });
}

function displayPipelineResults(data) {
    // Display pipeline stages
    const stagesContainer = document.getElementById('pipelineStages');
    stagesContainer.innerHTML = '';

    data.pipeline_stages.forEach((stage, index) => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.innerHTML = `
            ${stage}
            <span class="badge bg-primary rounded-pill">${index + 1}</span>
        `;
        stagesContainer.appendChild(li);
    });

    // Display sample results
    const resultsContainer = document.getElementById('sampleResults');
    resultsContainer.innerHTML = '';

    Object.entries(data.pipeline_demo).forEach(([docType, result]) => {
        const classificationResult = result.classification_result;
        const confidence = Math.round(classificationResult.confidence * 100);

        const resultCard = document.createElement('div');
        resultCard.className = 'card mb-2';
        resultCard.innerHTML = `
            <div class="card-body p-2">
                <h6 class="card-title text-capitalize">${docType.replace('_', ' ')}</h6>
                <p class="card-text small">"${result.sample_text}"</p>
                <div class="d-flex justify-content-between align-items-center">
                    <span class="badge bg-${getConfidenceColor(confidence)}">${classificationResult.type}</span>
                    <small class="text-muted">${confidence}% confidence</small>
                </div>
                <small class="text-muted">${classificationResult.method}</small>
            </div>
        `;
        resultsContainer.appendChild(resultCard);
    });
}

function getConfidenceColor(confidence) {
    if (confidence >= 80) return 'success';
    if (confidence >= 60) return 'warning';
    return 'danger';
}

// Analytics functions
function loadAnalytics() {
  fetch('/api/stats')
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      // ✅ Now 'data' is available here
      updateStatsCards(data);
      updateTypeChart(data.type_distribution);
      updateRoutingSummary(data.type_distribution);
    })
    .catch(error => {
      console.error('Error loading dashboard stats:', error);
    });
}

function showMessage(msg, type = 'info') {
    showAlert(msg, type);
}

function updateStatsCards(stats) {
    const elements = {
        'totalDocs': stats.total_documents,
        'completedDocs': stats.completed_documents,
        'processingDocs': stats.processing_documents,
        'errorDocs': stats.error_documents
    };

    Object.keys(elements).forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = elements[id] || 0;
        }
    });
}

function updateTypeChart(typeDistribution) {
    const ctx = document.getElementById('typeChart');
    if (!ctx) return;

    const labels = Object.keys(typeDistribution);
    const data = Object.values(typeDistribution);

    if (typeChart) {
        typeChart.destroy();
    }

    typeChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#0d6efd', '#6f42c1', '#d63384', '#dc3545', '#fd7e14',
                    '#ffc107', '#198754', '#20c997', '#0dcaf0', '#6c757d'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function updateRoutingSummary(typeDistribution) {
    const routingSummary = document.getElementById('routingSummary');
    if (!routingSummary) return;

    const routingMap = {
        'Invoice': 'Accounting',
        'Resume': 'Human Resources',
        'Contract': 'Legal',
        'Bank Statement': 'Finance',
        'Other': 'General Office'
    };

    let html = '';
    Object.keys(typeDistribution).forEach(type => {
        const count = typeDistribution[type];
        const department = routingMap[type] || 'General Office';
        html += `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span><strong>${type}:</strong> ${department}</span>
                <span class="badge bg-primary">${count}</span>
            </div>
        `;
    });

    if (html) {
        routingSummary.innerHTML = html;
    } else {
        routingSummary.innerHTML = '<p class="text-muted">No documents processed yet</p>';
    }
}

function refreshDashboard() {
    loadDashboardStats();
    location.reload(); // Refresh the table data
}

function loadDashboardStats() {
    console.log("Loading dashboard stats...");

    fetch('/api/dashboard_stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('totalDocs').innerText = data.total_documents || 0;
            document.getElementById('completedDocs').innerText = data.completed_documents || 0;
            document.getElementById('processingDocs').innerText = data.processing_documents || 0;
            document.getElementById('errorDocs').innerText = data.error_documents || 0;
        })
        .catch(error => {
            console.error('Error loading dashboard stats:', error);
            showAlert('Failed to load dashboard stats: ' + error.message, 'danger');
        });
}
function showReclassifyModal(documentId, currentType) {
    const modal = new bootstrap.Modal(document.getElementById('reclassifyModal'));
    document.getElementById('reclassifyDocId').value = documentId;
    document.getElementById('currentType').textContent = currentType;
    document.getElementById('newType').value = '';
    modal.show();
}

function submitReclassification() {
    const documentId = document.getElementById('reclassifyDocId').value;
    const newType = document.getElementById('newType').value;

    if (!newType) {
        alert('Please select a new document type');
        return;
    }

    fetch(`/reclassify/${documentId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ new_type: newType })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('reclassifyModal'));
            modal.hide();

            // Refresh the page to show updated data
            location.reload();
        } else {
            throw new Error(data.error || 'Reclassification failed');
        }
    })
    .catch(error => {
        console.error('Reclassification error:', error);
        alert('Reclassification failed: ' + error.message);
    });
}

document.getElementById('chat-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        const message = this.value.trim();
        if (message) {
            const messagesDiv = document.getElementById('chat-messages');
            messagesDiv.innerHTML += `<div><strong>You:</strong> ${message}</div>`;
            this.value = '';

            fetch('/api/chatbot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message })
            })
            .then(res => res.json())
            .then(data => {
                messagesDiv.innerHTML += `<div><strong>Bot:</strong> ${data.response}</div>`;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            })
            .catch(() => {
                messagesDiv.innerHTML += `<div><strong>Bot:</strong> Error processing your message.</div>`;
            });
        }
    }
});
