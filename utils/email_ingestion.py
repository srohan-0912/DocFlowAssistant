import os
import email
import imaplib
import logging
import mimetypes
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl
from werkzeug.utils import secure_filename
import uuid
import json

logger = logging.getLogger(__name__)

class EmailDocumentIngestion:
    """Email integration for automatic document ingestion"""
    
    def __init__(self, upload_folder: str = "uploads"):
        self.upload_folder = upload_folder
        self.processed_emails_file = "processed_emails.txt"
        self.config_file = "email_config.json"
        self.supported_attachments = {
            '.pdf', '.docx', '.jpg', '.jpeg', '.png', '.doc', '.txt', '.xls', '.xlsx', '.ppt', '.pptx'
        }
        
        # Email configuration - these should be set via environment variables
        self.imap_server = None
        self.imap_port = 993
        self.smtp_server = None
        self.smtp_port = 587
        self.email_address = None
        self.email_password = None
        
        # Connection settings
        self.connection_timeout = 30
        self.max_retries = 3
        self.retry_delay = 5
        self.last_check_time = None
        self.monitoring_active = False
        self.monitoring_thread = None
        
        self._load_email_config()
        self._start_background_monitoring()
    
    def _load_email_config(self):
        """Load email configuration from environment variables and config file"""
        # Try environment variables first
        self.imap_server = os.environ.get('EMAIL_IMAP_SERVER')
        self.smtp_server = os.environ.get('EMAIL_SMTP_SERVER')
        self.email_address = os.environ.get('EMAIL_ADDRESS')
        self.email_password = os.environ.get('EMAIL_PASSWORD')
        
        # Load from config file if environment variables not set
        if not self.email_address and os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.email_address = config.get('email_address')
                    self.email_password = config.get('email_password')
                    self.imap_server = config.get('imap_server')
                    self.smtp_server = config.get('smtp_server')
            except Exception as e:
                logger.error(f"Error loading email config file: {str(e)}")
        
        # Set default servers for common providers
        if self.email_address and not self.imap_server:
            domain = self.email_address.split('@')[1].lower()
            if 'gmail' in domain:
                self.imap_server = 'imap.gmail.com'
                self.imap_port = 993
                self.smtp_server = 'smtp.gmail.com'
                self.smtp_port = 587
            elif 'outlook' in domain or 'hotmail' in domain or 'live' in domain:
                self.imap_server = 'outlook.office365.com'
                self.imap_port = 993
                self.smtp_server = 'smtp.office365.com'
                self.smtp_port = 587
            elif 'yahoo' in domain:
                self.imap_server = 'imap.mail.yahoo.com'
                self.imap_port = 993
                self.smtp_server = 'smtp.mail.yahoo.com'
                self.smtp_port = 587
    
    def save_email_config(self, email_address: str, email_password: str, imap_server: str = None, smtp_server: str = None):
        """Save email configuration to config file"""
        try:
            config = {
                'email_address': email_address,
                'email_password': email_password,
                'imap_server': imap_server,
                'smtp_server': smtp_server,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Update instance variables
            self.email_address = email_address
            self.email_password = email_password
            if imap_server:
                self.imap_server = imap_server
            if smtp_server:
                self.smtp_server = smtp_server
            
            # Auto-detect servers if not provided
            self._load_email_config()
            
            logger.info("Email configuration saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving email config: {str(e)}")
            return False
    
    def is_configured(self) -> bool:
        """Check if email integration is properly configured"""
        return all([
            self.imap_server,
            self.email_address,
            self.email_password
        ])
    
    def get_configuration_status(self) -> Dict[str, any]:
        """Get current email configuration status"""
        return {
            'is_configured': self.is_configured(),
            'email_address': self.email_address if self.email_address else 'Not set',
            'imap_server': self.imap_server if self.imap_server else 'Not set',
            'smtp_server': self.smtp_server if self.smtp_server else 'Not set',
            'missing_vars': [
                var for var in ['EMAIL_ADDRESS', 'EMAIL_PASSWORD', 'EMAIL_IMAP_SERVER']
                if not os.environ.get(var)
            ]
        }
    
    def connect_to_email(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to email server using IMAP with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if not self.is_configured():
                    logger.error("Email not configured. Missing configuration.")
                    return None
                
                logger.info(f"Connecting to {self.imap_server}:{self.imap_port} (attempt {attempt + 1})")
                
                # Create SSL context
                context = ssl.create_default_context()
                
                # Connect to IMAP server with timeout
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
                mail.sock.settimeout(self.connection_timeout)
                
                # Login with credentials
                mail.login(self.email_address, self.email_password)
                
                logger.info(f"Successfully connected to email server: {self.imap_server}")
                return mail
                
            except imaplib.IMAP4.error as e:
                error_msg = str(e).lower()
                if 'authentication failed' in error_msg or 'invalid credentials' in error_msg:
                    logger.error("Authentication failed. Check email credentials.")
                    if 'gmail' in self.imap_server.lower():
                        logger.error("For Gmail, make sure to use an App Password instead of your regular password.")
                    return None
                logger.error(f"IMAP error on attempt {attempt + 1}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Connection error on attempt {attempt + 1}: {str(e)}")
                
            if attempt < self.max_retries - 1:
                logger.info(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
        
        logger.error(f"Failed to connect after {self.max_retries} attempts")
        return None
    
    def get_processed_email_ids(self) -> set:
        """Get list of already processed email IDs"""
        try:
            if os.path.exists(self.processed_emails_file):
                with open(self.processed_emails_file, 'r') as f:
                    return set(line.strip() for line in f.readlines())
            return set()
        except Exception as e:
            logger.error(f"Error reading processed emails file: {str(e)}")
            return set()
    
    def mark_email_processed(self, email_id: str):
        """Mark an email as processed"""
        try:
            with open(self.processed_emails_file, 'a') as f:
                f.write(f"{email_id}\n")
        except Exception as e:
            logger.error(f"Error marking email as processed: {str(e)}")
    
    def check_for_new_documents(self, mailbox: str = 'INBOX', max_emails: int = 50) -> List[Dict]:
        """Check for new emails with document attachments"""
        documents_found = []
        processed_count = 0
        errors = []
        
        mail = self.connect_to_email()
        if not mail:
            return documents_found
        
        try:
            # Select mailbox
            result, data = mail.select(mailbox)
            if result != 'OK':
                logger.error(f"Failed to select mailbox {mailbox}")
                return documents_found
            
            # Search for recent unread emails (last 7 days)
            since_date = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
            search_criteria = f'(UNSEEN SINCE {since_date})'
            
            result, email_ids = mail.search(None, search_criteria)
            
            if result != 'OK':
                logger.error("Failed to search emails")
                return documents_found
            
            email_list = email_ids[0].split()
            total_emails = len(email_list)
            
            if total_emails == 0:
                logger.info("No unread emails found")
                self.last_check_time = datetime.utcnow()
                return documents_found
            
            logger.info(f"Found {total_emails} unread emails to process")
            processed_ids = self.get_processed_email_ids()
            
            # Process emails (limit to max_emails to prevent overload)
            for i, email_id in enumerate(email_list[:max_emails]):
                try:
                    email_id_str = email_id.decode('utf-8')
                    
                    if email_id_str in processed_ids:
                        processed_count += 1
                        continue
                    
                    # Fetch email with timeout protection
                    result, email_data = mail.fetch(email_id, '(RFC822)')
                    
                    if result != 'OK':
                        errors.append(f"Failed to fetch email {email_id_str}")
                        continue
                    
                    # Parse email
                    email_message = email.message_from_bytes(email_data[0][1])
                    documents = self._process_email_attachments(email_message, email_id_str)
                    
                    if documents:
                        documents_found.extend(documents)
                        logger.info(f"Found {len(documents)} documents in email {email_id_str}")
                    
                    # Mark as processed
                    self.mark_email_processed(email_id_str)
                    processed_count += 1
                    
                    # Progress logging
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i + 1}/{min(total_emails, max_emails)} emails")
                    
                except Exception as e:
                    error_msg = f"Error processing email {email_id_str}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            self.last_check_time = datetime.utcnow()
            logger.info(f"Email check complete: {len(documents_found)} documents found, {processed_count} emails processed")
            
            if errors:
                logger.warning(f"Encountered {len(errors)} errors during processing")
            
        except Exception as e:
            logger.error(f"Critical error during email check: {str(e)}")
        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass
        
        return documents_found
    
    def _process_email_attachments(self, email_message, email_id: str) -> List[Dict]:
        """Process attachments from an email message"""
        documents = []
        
        try:
            sender = email_message.get('From', 'Unknown')
            subject = email_message.get('Subject', 'No Subject')
            date = email_message.get('Date', '')
            
            logger.info(f"Processing email from {sender} with subject: {subject}")
            
            # Process multipart message
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_disposition() == 'attachment':
                        filename = part.get_filename()
                        
                        if filename and self._is_supported_document(filename):
                            # Save attachment
                            saved_path = self._save_attachment(part, filename, email_id)
                            
                            if saved_path:
                                document_info = {
                                    'file_path': saved_path,
                                    'original_filename': filename,
                                    'source': 'email',
                                    'email_sender': sender,
                                    'email_subject': subject,
                                    'email_date': date,
                                    'email_id': email_id,
                                    'mime_type': part.get_content_type() or 'application/octet-stream'
                                }
                                documents.append(document_info)
                                
        except Exception as e:
            logger.error(f"Error processing email attachments: {str(e)}")
        
        return documents
    
    def _is_supported_document(self, filename: str) -> bool:
        """Check if the file is a supported document type"""
        if not filename:
            return False
        
        file_ext = os.path.splitext(filename.lower())[1]
        return file_ext in self.supported_attachments
    
    def _save_attachment(self, part, filename: str, email_id: str) -> Optional[str]:
        """Save email attachment to upload folder"""
        try:
            # Create secure filename
            secure_name = secure_filename(filename)
            unique_filename = f"{uuid.uuid4()}_{secure_name}"
            file_path = os.path.join(self.upload_folder, unique_filename)
            
            # Ensure upload directory exists
            os.makedirs(self.upload_folder, exist_ok=True)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(part.get_payload(decode=True))
            
            file_size = os.path.getsize(file_path)
            logger.info(f"Saved attachment: {filename} ({file_size} bytes) -> {file_path}")
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving attachment {filename}: {str(e)}")
            return None
    
    def send_processing_notification(self, recipient: str, document_info: Dict, processing_result: Dict):
        """Send email notification about document processing results"""
        try:
            if not self.smtp_server or not self.email_address or not self.email_password:
                logger.warning("SMTP not configured, cannot send notification")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = recipient
            msg['Subject'] = f"Document Processing Complete: {document_info.get('original_filename', 'Document')}"
            
            # Create email body
            body = self._create_notification_body(document_info, processing_result)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.email_address, self.email_password)
                server.sendmail(self.email_address, recipient, msg.as_string())
            
            logger.info(f"Sent processing notification to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return False
    
    def _create_notification_body(self, document_info: Dict, processing_result: Dict) -> str:
        """Create HTML email body for processing notification"""
        status = processing_result.get('status', 'unknown')
        doc_type = processing_result.get('document_type', 'Unknown')
        confidence = processing_result.get('confidence_score', 0)
        routed_to = processing_result.get('routed_to', 'Not routed')
        
        status_color = {
            'completed': '#28a745',
            'error': '#dc3545',
            'processing': '#ffc107'
        }.get(status, '#6c757d')
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                    DocuFlow AI - Document Processing Report
                </h2>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #495057;">Document Information</h3>
                    <p><strong>Filename:</strong> {document_info.get('original_filename', 'Unknown')}</p>
                    <p><strong>Source:</strong> Email from {document_info.get('email_sender', 'Unknown')}</p>
                    <p><strong>Subject:</strong> {document_info.get('email_subject', 'No subject')}</p>
                    <p><strong>Processed:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
                <div style="background-color: #fff; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #495057;">Processing Results</h3>
                    <p><strong>Status:</strong> <span style="color: {status_color}; font-weight: bold;">{status.title()}</span></p>
                    <p><strong>Document Type:</strong> {doc_type}</p>
                    <p><strong>Confidence:</strong> {int(confidence * 100) if confidence else 0}%</p>
                    <p><strong>Routed To:</strong> {routed_to}</p>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d;">
                    <p>This is an automated notification from DocuFlow AI document processing system.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return body
    
    def setup_email_monitoring(self, check_interval_minutes: int = 15):
        """Set up automatic email monitoring (for production deployment)"""
        try:
            import schedule
            import time
            import threading
            
            def email_check_job():
                logger.info("Checking for new email documents...")
                new_documents = self.check_for_new_documents()
                
                if new_documents:
                    logger.info(f"Found {len(new_documents)} new documents from email")
                    # Here you would typically trigger the document processing pipeline
                    for doc in new_documents:
                        logger.info(f"New document: {doc['original_filename']} from {doc['email_sender']}")
                else:
                    logger.info("No new email documents found")
            
            # Schedule email checking
            schedule.every(check_interval_minutes).minutes.do(email_check_job)
            
            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute for scheduled jobs
            
            # Run scheduler in background thread
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            
            logger.info(f"Email monitoring started - checking every {check_interval_minutes} minutes")
            return True
            
        except ImportError:
            logger.error("Schedule library not available for email monitoring")
            return False
        except Exception as e:
            logger.error(f"Error setting up email monitoring: {str(e)}")
            return False
    
    def _start_background_monitoring(self, check_interval_minutes: int = 15):
        """Start background email monitoring thread"""
        if self.monitoring_active:
            return
        
        def monitor_emails():
            while self.monitoring_active:
                try:
                    if self.is_configured():
                        logger.info("Background email check starting...")
                        new_documents = self.check_for_new_documents()
                        
                        if new_documents:
                            logger.info(f"Background check found {len(new_documents)} new documents")
                            # Here you could trigger document processing pipeline
                            # For now, just log the findings
                            for doc in new_documents:
                                logger.info(f"New document queued: {doc['original_filename']} from {doc['email_sender']}")
                        else:
                            logger.debug("Background check: no new documents found")
                    else:
                        logger.debug("Email not configured, skipping background check")
                        
                except Exception as e:
                    logger.error(f"Background email monitoring error: {str(e)}")
                
                # Wait for next check
                for _ in range(check_interval_minutes * 60):  # Convert minutes to seconds
                    if not self.monitoring_active:
                        break
                    time.sleep(1)
        
        try:
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=monitor_emails, daemon=True)
            self.monitoring_thread.start()
            logger.info(f"Background email monitoring started (interval: {check_interval_minutes} minutes)")
        except Exception as e:
            logger.error(f"Failed to start background monitoring: {str(e)}")
            self.monitoring_active = False
    
    def stop_monitoring(self):
        """Stop background email monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        logger.info("Background email monitoring stopped")
    
    def get_monitoring_status(self) -> Dict[str, any]:
        """Get current monitoring status"""
        return {
            'monitoring_active': self.monitoring_active,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'thread_alive': self.monitoring_thread.is_alive() if self.monitoring_thread else False,
            'is_configured': self.is_configured()
        }
    
    def test_connection(self) -> Dict[str, any]:
        """Test email connection and return detailed status"""
        test_result = {
            'success': False,
            'message': '',
            'details': {},
            'suggestions': []
        }
        
        try:
            if not self.is_configured():
                test_result['message'] = 'Email not configured'
                test_result['suggestions'].append('Set up email credentials')
                return test_result
            
            # Test IMAP connection
            mail = self.connect_to_email()
            if not mail:
                test_result['message'] = 'Failed to connect to email server'
                if 'gmail' in self.imap_server.lower():
                    test_result['suggestions'].extend([
                        'Enable 2-factor authentication on Gmail',
                        'Generate an App Password from Google Account settings',
                        'Use the App Password instead of your regular password'
                    ])
                return test_result
            
            # Test mailbox access
            result, data = mail.select('INBOX')
            if result == 'OK':
                message_count = int(data[0])
                test_result['details']['inbox_messages'] = message_count
                
                # Test recent email search
                since_date = (datetime.now() - timedelta(days=1)).strftime('%d-%b-%Y')
                result, email_ids = mail.search(None, f'SINCE {since_date}')
                
                if result == 'OK':
                    recent_count = len(email_ids[0].split()) if email_ids[0] else 0
                    test_result['details']['recent_messages'] = recent_count
                    
                    test_result['success'] = True
                    test_result['message'] = f'Connection successful! Found {message_count} messages in inbox, {recent_count} recent messages'
                else:
                    test_result['message'] = 'Connected but failed to search emails'
            else:
                test_result['message'] = 'Connected but failed to access inbox'
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            test_result['message'] = f'Connection test failed: {str(e)}'
            logger.error(f"Email connection test error: {str(e)}")
        
        return test_result

# Global email ingestion instance
email_ingestion = EmailDocumentIngestion()