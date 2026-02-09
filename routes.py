from flask_login import login_required, current_user

routing_keywords = {
    "Accounting": ["invoice"],
    "Finance": ["bank", "statement"],
    "Legal": ["contract", "agreement", "party"],  
    "Human Resources": ["resume", "cv"]
}

def get_routing_department(label: str, extracted_text: str = "") -> str:
    label = label.lower()
    extracted_text = extracted_text.lower()

    for dept, keywords in routing_keywords.items():
        if any(keyword in label for keyword in keywords) or any(keyword in extracted_text for keyword in keywords):
            return dept
    return "General Office"

import os
import uuid
from datetime import datetime
from flask import render_template, request, jsonify, current_app, flash, redirect, url_for
from werkzeug.utils import secure_filename
from app import app, db
from models import Document, User
from utils.ocr_extractor import extract_text, clean_text
from utils.classifier import classify_document
from utils.router import route_document
from utils.email_ingestion import email_ingestion
from utils.hybrid_classifier import hybrid_classifier
from flask_login import login_required, login_user, logout_user, current_user
from flask import Flask, request, jsonify, render_template, session
from datetime import timedelta
import plotly.graph_objs as go
import plotly
import json
import pandas as pd
from sqlalchemy import func
from utils.genai_utils import summarize_text



ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}

from flask import jsonify
from models import Document

@app.route('/api/dashboard_stats')
@login_required
def dashboard_stats():
    try:
        total = Document.query.count()
        completed = Document.query.filter_by(status='completed').count()
        processing = Document.query.filter_by(status='processing').count()
        error = Document.query.filter_by(status='error').count()

        return jsonify({
            'total_documents': total,
            'completed_documents': completed,
            'processing_documents': processing,
            'error_documents': error
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = 30  # documents per page
    documents = Document.query.order_by(Document.uploaded_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('dashboard.html', documents=documents)

from datetime import datetime
import pytz

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)


@app.route('/email')
def email_integration():
    return render_template('email_integration.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        try:
            # Generate unique filename
            original_filename = secure_filename(file.filename)
            filename = f"{uuid.uuid4()}_{original_filename}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

            # Save file
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            # Create database record
            document = Document(
                filename=filename,
                original_filename=original_filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=file.content_type or 'application/octet-stream',
                status='uploaded',
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(document)
            db.session.commit()

            return jsonify({
                'success': True,
                'document_id': document.id,
                'filename': original_filename,
                'message': 'File uploaded successfully'
            })

        except Exception as e:
            current_app.logger.error(f"Upload error: {str(e)}")
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file type. Allowed: PDF, DOCX, JPG, PNG'}), 400

@app.route('/process/<int:document_id>', methods=['POST'])
def process_document(document_id):
    document = Document.query.get_or_404(document_id)

    try:
        # Update status to processing
        document.status = 'processing'
        db.session.commit()

        # Step 1: Extract text using OCR
        current_app.logger.info(f"Extracting text from {document.filename}")
        extracted_text = extract_text(document.file_path)
        extracted_text = clean_text(extracted_text)  #Final cleanup for classifier

        if not extracted_text.strip():
            raise Exception("No text could be extracted from the document")

        document.extracted_text = extracted_text
        db.session.commit()

        # Step 2: Classify document using hybrid + GenAI
        current_app.logger.info(f"Classifying document {document.filename} using hybrid classifier")
        classification_result = hybrid_classifier.classify_document(extracted_text)
        document.document_type = classification_result.get('type', 'unknown')
        document.confidence_score = classification_result.get('confidence', 0.0)
        document.classification_method = classification_result.get('method', 'hybrid')


        # 3. Summarize using GPT-4
        current_app.logger.info(f"Generating summary for {document.filename}")
        document.summary = summarize_text(extracted_text)

        db.session.commit()


        # Step 3: Route document
        current_app.logger.info(f"Routing document {document.filename}")
        routing_result = route_document(
            document.file_path, 
            document.document_type,
            current_app.config['ROUTED_FOLDER']
        )

        document.routed_to = routing_result['department']
        document.routed_path = routing_result['path']
        document.status = 'completed'
        document.processed_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Database error saving final results: {str(e)}")
            return jsonify({'success': False, 'error': 'Database connection issue'}), 500

        return jsonify({
    'success': True,
    'document_id': document.id,
    'filename': document.filename,
    'extracted_text': document.extracted_text[:500] + '...' if len(document.extracted_text) > 500 else document.extracted_text,
    'classification': {
        'type': document.document_type or "Unknown",
        'confidence': document.confidence_score or 0.0,
        'method': document.classification_method or "N/A"
    },
    'routing': {
        'department': document.routed_to or "Unassigned",
        'path': document.routed_path or "N/A"
    }
})


    except Exception as e:
        current_app.logger.error(f"Processing error for document {document_id}: {str(e)}")
        try:
            db.session.rollback()
            document.status = 'error'
            document.error_message = str(e)
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            current_app.logger.error(f"Database error saving error status: {str(db_error)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reclassify/<int:document_id>', methods=['POST'])
def reclassify_document(document_id):
    document = Document.query.get_or_404(document_id)
    data = request.get_json()

    if not data or 'new_type' not in data:
        return jsonify({'error': 'New document type is required'}), 400

    try:
        # Store original classification if not already done
        if not document.manually_reclassified:
            document.original_classification = document.document_type

        # Update classification
        document.document_type = data['new_type']
        document.manually_reclassified = True
        document.confidence_score = 1.0  # Manual classification has 100% confidence

        # Re-route document
        routing_result = route_document(
            document.file_path, 
            document.document_type,
            current_app.config['ROUTED_FOLDER']
        )

        document.routed_to = routing_result['department']
        document.routed_path = routing_result['path']
        db.session.commit()

        return jsonify({
            'success': True,
            'document': document.to_dict(),
            'routing': routing_result
        })

    except Exception as e:
        current_app.logger.error(f"Reclassification error: {str(e)}")
        return jsonify({'error': f'Reclassification failed: {str(e)}'}), 500

@app.route('/api/documents')
def get_documents():
    documents = Document.query.order_by(Document.uploaded_at.desc()).all()
    return jsonify([doc.to_dict() for doc in documents])

from flask import jsonify
from collections import defaultdict

@app.route('/api/stats')
def get_document_stats():
    from models import Document

    try:
        total = Document.query.count()
        completed = Document.query.filter_by(status='completed').count()
        processing = Document.query.filter_by(status='processing').count()
        error = Document.query.filter_by(status='error').count()

        valid_types = ['Invoice', 'Contract', 'Resume', 'Bank Statement', 'Other']
        type_distribution = {key: 0 for key in valid_types}

        docs = Document.query.all()
        for doc in docs:
            label = (doc.document_type or '').strip().title()
            if label in type_distribution:
                type_distribution[label] += 1
            else:
                type_distribution['Other'] += 1

        return jsonify({
            "total_documents": total,
            "completed_documents": completed,
            "processing_documents": processing,
            "error_documents": error,
            "type_distribution": type_distribution
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/email/config')
def email_config():
    """Get email integration configuration status"""
    config_status = email_ingestion.get_configuration_status()
    return jsonify(config_status)

@app.route('/email/check', methods=['POST'])
def check_email():
    """Manually trigger email check for new documents"""
    try:
        if not email_ingestion.is_configured():
            return jsonify({
                'error': 'Email integration not configured',
                'config_status': email_ingestion.get_configuration_status()
            }), 400

        new_documents = email_ingestion.check_for_new_documents()

        # Process each found document
        processed_documents = []
        for doc_info in new_documents:
            try:
                # Create database record
                document = Document(
                    filename=os.path.basename(doc_info['file_path']),
                    original_filename=doc_info['original_filename'],
                    file_path=doc_info['file_path'],
                    file_size=os.path.getsize(doc_info['file_path']),
                    mime_type=doc_info['mime_type'],
                    status='uploaded'
                )
                db.session.add(document)
                db.session.flush()  # Get the ID

                # Start processing
                document.status = 'processing'
                db.session.commit()

                # Extract text
                extracted_text = extract_text(document.file_path)
                document.extracted_text = extracted_text
                current_app.logger.info(f"[DEBUG] Cleaned OCR Text (preview): {extracted_text[:300]}")


                # Classify document using hybrid classifier
                classification_result = hybrid_classifier.classify_document(extracted_text)
                document.document_type = classification_result.get('type', 'unknown')
                document.confidence_score = classification_result.get('confidence', 0.0)
                document.classification_method = classification_result.get('method', 'hybrid')

                # Route document
                routing_result = route_document(
                    document.file_path,
                    document.document_type,
                    current_app.config['ROUTED_FOLDER']
                )

                document.routed_to = routing_result['department']
                document.routed_path = routing_result['path']
                document.status = 'completed'
                document.processed_at = datetime.utcnow()

                db.session.commit()

                processed_doc = {
                    'id': document.id,
                    'filename': document.original_filename,
                    'email_sender': doc_info.get('email_sender', 'Unknown'),
                    'document_type': document.document_type,
                    'confidence': document.confidence_score,
                    'routed_to': document.routed_to,
                    'status': 'completed'
                }
                processed_documents.append(processed_doc)

                # Send notification to sender if configured
                sender_email = doc_info.get('email_sender', '').split('<')[-1].split('>')[0]
                if sender_email and '@' in sender_email:
                    email_ingestion.send_processing_notification(
                        sender_email,
                        doc_info,
                        {
                            'status': 'completed',
                            'document_type': document.document_type,
                            'confidence_score': document.confidence_score,
                            'routed_to': document.routed_to
                        }
                    )

            except Exception as e:
                current_app.logger.error(f"Error processing email document {doc_info['original_filename']}: {str(e)}")
                if 'document' in locals():
                    document.status = 'error'
                    db.session.commit()

        return jsonify({
            'success': True,
            'documents_found': len(new_documents),
            'documents_processed': len(processed_documents),
            'processed_documents': processed_documents
        })

    except Exception as e:
        current_app.logger.error(f"Email check error: {str(e)}")
        return jsonify({'error': f'Email check failed: {str(e)}'}), 500

@app.route('/email/setup', methods=['POST'])
def setup_email():
    """Setup or update email configuration"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No configuration data provided'}), 400

    try:
        required_fields = ['email_address', 'email_password']

        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Save configuration using the email ingestion class
        success = email_ingestion.save_email_config(
            email_address=data['email_address'],
            email_password=data['email_password'],
            imap_server=data.get('imap_server'),
            smtp_server=data.get('smtp_server')
        )

        if success:
            return jsonify({
                'success': True,
                'message': 'Email configuration saved successfully',
                'configured': email_ingestion.is_configured()
            })
        else:
            return jsonify({'error': 'Failed to save email configuration'}), 500

    except Exception as e:
        current_app.logger.error(f"Email setup error: {str(e)}")
        return jsonify({'error': f'Setup failed: {str(e)}'}), 500

@app.route('/email/test', methods=['POST'])
def test_email_connection():
    """Test email connection"""
    try:
        test_result = email_ingestion.test_connection()

        status_code = 200 if test_result['success'] else 400
        return jsonify(test_result), status_code

    except Exception as e:
        current_app.logger.error(f"Email test error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Test failed: {str(e)}',
            'details': {},
            'suggestions': ['Check your internet connection', 'Verify email server settings']
        }), 500

@app.route('/email/monitoring/status')
def get_monitoring_status():
    """Get email monitoring status"""
    try:
        status = email_ingestion.get_monitoring_status()
        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Monitoring status error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/email/monitoring/toggle', methods=['POST'])
def toggle_monitoring():
    """Toggle email monitoring on/off"""
    try:
        data = request.get_json()
        enable = data.get('enable', True)

        if enable and not email_ingestion.monitoring_active:
            email_ingestion._start_background_monitoring()
            message = 'Email monitoring started'
        elif not enable and email_ingestion.monitoring_active:
            email_ingestion.stop_monitoring()
            message = 'Email monitoring stopped'
        else:
            message = f'Email monitoring already {"enabled" if enable else "disabled"}'

        return jsonify({
            'success': True,
            'message': message,
            'monitoring_active': email_ingestion.monitoring_active
        })

    except Exception as e:
        current_app.logger.error(f"Monitoring toggle error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        from models import User
        email = request.form.get('email')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember, duration=timedelta(days=7))
            flash('Welcome back!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        from models import User
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')

        # Create new user
        user = User(
            username=username,
            email=email,
            role='user'
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/analytics')
# @login_required
def analytics():
    return render_template('analytics.html')

# Advanced Analytics API Routes
from datetime import datetime, timedelta
from sqlalchemy import func
from flask import jsonify, current_app

@app.route('/api/analytics/charts')
def analytics_charts():
    try:
        # Step 1: Fetch raw counts
        type_stats = db.session.query(
            Document.document_type,
            db.func.count(Document.id)
        ).filter(
            Document.document_type.isnot(None)
        ).group_by(Document.document_type).all()

        # Step 2: Normalize document types
        valid_types = ['Invoice', 'Contract', 'Resume', 'Bank Statement', 'Other']
        normalized_distribution = {key: 0 for key in valid_types}

        for doc_type, count in type_stats:
            label = (doc_type or '').strip().title()
            if label in normalized_distribution:
                normalized_distribution[label] += count
            else:
                normalized_distribution['Other'] += count

        type_distribution = normalized_distribution


        # 2️⃣ Processing Trends (Last 7 Days) - WITH Full DateTime in IST
        week_ago = datetime.utcnow() - timedelta(days=7)

        trends = db.session.query(
            db.func.strftime('%Y-%m-%d %H:%M:%S', db.func.datetime(Document.uploaded_at, '+5 hours', '+30 minutes')).label('datetime'),
            db.func.count(Document.id).label('count')
        ).filter(
            Document.uploaded_at >= week_ago
        ).group_by(
            'datetime'
        ).order_by(
            'datetime'
        ).all()

        processing_trends = {
            'dates': [trend.datetime for trend in trends],
            'counts': [trend.count for trend in trends]
        }

        # 3️⃣ Classification Method Accuracy (Simulated)
        classification_methods = ['Rule-based', 'Machine Learning', 'Hybrid']
        accuracy_scores = [85, 92, 96]

        # 4️⃣ Routing Distribution
        routing_stats = db.session.query(
            Document.routed_to,
            db.func.count(Document.id)
        ).filter(
            Document.routed_to.isnot(None)
        ).group_by(Document.routed_to).all()

        routing_distribution = dict(routing_stats) if routing_stats else {}

        return jsonify(
            type_distribution=type_distribution,
            processing_trends=processing_trends,
            routing_distribution=routing_distribution,
            classification_methods=classification_methods,
            accuracy_scores=accuracy_scores
        )

    except Exception as e:
        current_app.logger.error(f"Analytics charts error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pipeline-demo')
@login_required
def pipeline_demo():
    demo_result = {
        "success": True,
        "pipeline_stages": ["Ingested", "Extracted", "Classified", "Routed"],
        "pipeline_demo": {
            "invoice": {
                "sample_text": "Invoice #12345 from ABC Corp.",
                "classification_result": {
                    "type": "Invoice",
                    "confidence": 0.95,
                    "method": "LLM + Classifier"
                }
            },
            "resume": {
                "sample_text": "John Doe, Software Engineer at XYZ Inc.",
                "classification_result": {
                    "type": "Resume",
                    "confidence": 0.88,
                    "method": "Zero-shot LLM"
                }
            },
            "contract": {
                "sample_text": "Service Agreement between two parties...",
                "classification_result": {
                    "type": "Contract",
                    "confidence": 0.91,
                    "method": "Rule-based"
                }
            },
            "bank_statement": {
                "sample_text": "Account Number 987654321. Balance: $3,500...",
                "classification_result": {
                    "type": "Bank Statement",
                    "confidence": 0.83,
                    "method": "Keyword Match"
                }
            }
        }
    }
    return jsonify(demo_result)


@app.route('/api/analytics/performance')
@login_required
def analytics_performance():
    try:
        # Calculate performance metrics
        total_docs = Document.query.count()
        completed_docs = Document.query.filter_by(status='completed').count()

        # Average processing time
        avg_time_result = db.session.query(
            db.func.avg(Document.processing_time)
        ).filter(
            Document.processing_time.isnot(None)
        ).scalar()

        avg_processing_time = float(avg_time_result) if avg_time_result else 0.0

        # OCR success rate (documents with extracted text)
        ocr_success = Document.query.filter(
            Document.extracted_text.isnot(None),
            Document.extracted_text != ''
        ).count()
        ocr_success_rate = (ocr_success / total_docs) if total_docs > 0 else 0

        # Classification accuracy (high confidence classifications)
        high_confidence = Document.query.filter(
            Document.confidence_score >= 0.8
        ).count()
        completed_docs = Document.query.filter_by(status='completed').count()

        high_confidence = Document.query.filter(
            Document.status == 'completed',
            Document.confidence_score >= 0.8
        ).count()

        classification_accuracy = (high_confidence / completed_docs) if completed_docs > 0 else 0



        # Email and ML status
        email_configured = email_ingestion.is_configured()

        # Check if ML model is trained
        try:
            from utils.ml_classifier import ml_classifier
            ml_model_trained = ml_classifier.is_trained
        except:
            ml_model_trained = False

        return jsonify({
            'avg_processing_time': avg_processing_time,
            'ocr_success_rate': ocr_success_rate,
            'classification_accuracy': classification_accuracy,
            'completed_docs': completed_docs,
            'high_confidence': high_confidence,
            'email_configured': email_configured,
            'ml_model_trained': ml_model_trained
        })

    except Exception as e:
        current_app.logger.error(f"Analytics performance error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/activity')
@login_required
def analytics_activity():
    try:
        # Get recent documents with activity information
        recent_docs = Document.query.order_by(
            Document.uploaded_at.desc()
        ).limit(20).all()

        activities = []
        for doc in recent_docs:
            # Document upload activity
            activities.append({
                'type': 'upload',
                'title': f'Document uploaded: {doc.original_filename}',
                'details': f'File size: {doc.file_size} bytes, Type: {doc.mime_type}',
                'timestamp': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                'status': doc.status
            })

            # Processing completion activity
            if doc.processed_at:
                activities.append({
                    'type': 'classification',
                    'title': f'Document classified: {doc.document_type}',
                    'details': f'Confidence: {int((doc.confidence_score or 0) * 100)}%, Method: {doc.classification_method or "Unknown"}',
                    'timestamp': doc.processed_at.isoformat(),
                    'status': 'completed'
                })

            # Routing activity
            if doc.routed_to:
                activities.append({
                    'type': 'routing',
                    'title': f'Document routed to {doc.routed_to}',
                    'details': f'File: {doc.original_filename}',
                    'timestamp': doc.processed_at.isoformat() if doc.processed_at else None,
                    'status': 'completed'
                })

        # Sort activities by timestamp (most recent first)
        activities.sort(key=lambda x: x['timestamp'] or '', reverse=True)

        return jsonify(activities[:15])  # Return latest 15 activities

    except Exception as e:
        current_app.logger.error(f"Analytics activity error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    total_documents = Document.query.count()
    completed_documents = Document.query.filter_by(status='completed').count()
    error_documents = Document.query.filter_by(status='error').count()

    # Calculate average confidence
    avg_confidence_result = db.session.query(
        db.func.avg(Document.confidence_score)
    ).filter(
        Document.confidence_score.isnot(None)
    ).scalar()

    average_confidence = float(avg_confidence_result) if avg_confidence_result else 0.0

    # Document type distribution
    type_stats = db.session.query(
        Document.document_type, 
        db.func.count(Document.id)
    ).filter(
        Document.document_type.isnot(None)
    ).group_by(Document.document_type).all()

    return jsonify({
        'total_documents': total_documents,
        'completed_documents': completed_documents,
        'error_documents': error_documents,
        'processing_documents': total_documents - completed_documents - error_documents,
        'average_confidence': average_confidence,
        'type_distribution': dict(type_stats)
    })

@app.route('/api/chatbot', methods=['POST'])
@login_required
def chatbot_query():
    data = request.get_json()
    user_input = data.get('message')

    if not user_input:
        return jsonify({'response': 'Please provide a question.'}), 400

    response = handle_chat_query(user_input, user_id=current_user.id)
    return jsonify({'response': response})
