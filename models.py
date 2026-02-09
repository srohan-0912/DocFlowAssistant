from extensions import db, bcrypt  # ✅ Avoids circular import
from datetime import datetime
from flask_login import UserMixin
from utils.time_utils import get_ist_time

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # user, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    # Relationship to documents
    documents = db.relationship('Document', backref='user', lazy=True)

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Check password against hash"""
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=get_ist_time)


    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Processing status
    status = db.Column(db.String(50), default='uploaded')  # uploaded, processing, completed, error
    processed_at = db.Column(db.DateTime)
    processing_time = db.Column(db.Float)  # seconds

    # OCR and Classification results
    extracted_text = db.Column(db.Text)
    document_type = db.Column(db.String(100))
    confidence_score = db.Column(db.Float)
    classification_method = db.Column(db.String(50))  # rule_based, machine_learning, hybrid

    # Routing information
    routed_to = db.Column(db.String(100))
    routed_path = db.Column(db.String(500))

    # Manual override
    manual_classification = db.Column(db.String(100))
    manual_classification_by = db.Column(db.String(100))
    manual_classification_at = db.Column(db.DateTime)

    # Email source information
    email_source = db.Column(db.String(255))
    email_subject = db.Column(db.String(500))
    email_sender = db.Column(db.String(255))

    # Manual override tracking
    manually_reclassified = db.Column(db.Boolean, default=False)
    original_classification = db.Column(db.String(100))

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'status': self.status,
            'document_type': self.document_type,
            'confidence_score': self.confidence_score,
            'classification_method': self.classification_method,
            'routed_to': self.routed_to,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'processing_time': self.processing_time,
            'manually_reclassified': self.manually_reclassified,
            'email_source': self.email_source,
            'email_sender': self.email_sender,
            'user_id': self.user_id
        }
