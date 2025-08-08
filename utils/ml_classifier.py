import os
import logging
import pickle
import numpy as np

from typing import Dict, List, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.pipeline import Pipeline
import joblib

logger = logging.getLogger(__name__)

class MLDocumentClassifier:
    """Machine Learning based document classifier with TF-IDF and Random Forest"""
    
    def __init__(self, model_path: str = "models/ml_classifier.pkl"):
        self.model_path = model_path
        self.pipeline = None
        self.classes = ['Invoice', 'Resume', 'Contract', 'Bank Statement', 'Other']
        self.is_trained = False
        
        # Create models directory
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Load existing model if available
        self.load_model()
        
    def load_model(self):
        """Load pre-trained model if available"""
        try:
            if os.path.exists(self.model_path):
                self.pipeline = joblib.load(self.model_path)
                self.is_trained = True
                logger.info(f"Loaded ML classifier from {self.model_path}")
            else:
                logger.info("No pre-trained model found, will train on first use")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            self.pipeline = None
            self.is_trained = False
    
    def save_model(self):
        """Save trained model to disk"""
        try:
            if self.pipeline:
                joblib.dump(self.pipeline, self.model_path)
                logger.info(f"Saved ML classifier to {self.model_path}")
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
    
    def create_training_data(self) -> Tuple[List[str], List[str]]:
        """Create synthetic training data for document classification"""
        
        # Invoice training data
        invoice_texts = [
            "Invoice number INV-2024-001 Total amount due $1,250.00 Payment terms 30 days Due date 2024-02-15",
            "Bill to customer services rendered Amount $890.50 Invoice date January 15 2024 Payment due February 14",
            "Professional services invoice Total $2,100.00 Tax $210.00 Grand total $2,310.00 Remit payment to",
            "Invoice #12345 Billing address 123 Main St Amount due $567.89 Due date 03/15/2024",
            "Statement of charges Consulting fees $1,800 Travel expenses $200 Total invoice $2,000",
            "Medical services invoice Patient billing Insurance claim Amount owed $450.00 Payment terms net 15",
            "Legal services rendered Hours 12.5 Rate $300/hour Total $3,750 Invoice date February 1 2024",
            "Product invoice Quantity 50 Unit price $25.99 Subtotal $1,299.50 Sales tax $103.96 Total $1,403.46",
            "Utility bill Electric service Account number Invoice amount $189.34 Due date March 10 2024",
            "Software licensing invoice Annual subscription $599.00 Renewal date Auto-pay enabled"
        ]
        
        # Resume training data
        resume_texts = [
            "John Smith Software Engineer Experience Python Java JavaScript Education Bachelor Computer Science Skills",
            "Marketing Manager 5 years experience Digital marketing SEO social media Bachelor Business Administration",
            "Jane Doe Registered Nurse BSN degree 3 years ICU experience CPR certified References available",
            "Data Analyst SQL Python R statistical analysis Masters Statistics University of California",
            "Project Manager PMP certified Agile Scrum methodology 8 years experience leading teams",
            "Graphic Designer Adobe Creative Suite portfolio available Bachelor Fine Arts design experience",
            "Sales Representative Territory management CRM software quota achievement Bachelor Business",
            "Mechanical Engineer AutoCAD SolidWorks PE license 6 years manufacturing experience references",
            "Teacher Elementary education Masters Education 10 years classroom experience curriculum development",
            "Financial Analyst CPA Excel modeling financial reporting Bachelor Accounting MBA Finance"
        ]
        
        # Contract training data
        contract_texts = [
            "Service Agreement This agreement entered into between parties effective date Terms and conditions",
            "Employment contract Whereas company agrees to employ Terms of employment Salary benefits",
            "Lease agreement Landlord tenant property rental Monthly rent Security deposit Lease term",
            "Purchase agreement Buyer seller property Purchase price Closing date Title insurance",
            "Software license agreement End user license Permitted use Restrictions Termination",
            "Consulting agreement Independent contractor Services provided Compensation Confidentiality",
            "Partnership agreement Business partners Profit sharing Responsibilities Dissolution terms",
            "Non-disclosure agreement Confidential information Obligations Remedies Governing law",
            "Supply agreement Vendor customer Products delivery terms Payment Warranty",
            "Distribution agreement Distributor Territory Minimum sales Termination Marketing support"
        ]
        
        # Bank Statement training data
        bank_statement_texts = [
            "Bank statement Account number 123456789 Beginning balance $5,000.00 Ending balance $4,500.00",
            "Checking account Statement period January 1-31 2024 Deposits $2,000 Withdrawals $1,500",
            "Savings account Interest earned $12.50 Balance forward $10,000 Current balance $10,012.50",
            "Account summary Transaction history Debit credit Balance Available funds Overdraft protection",
            "Monthly statement Direct deposit Automatic payments ATM transactions Check clearing",
            "Credit card statement Previous balance $1,500 Payments $500 New charges $750 Current balance",
            "Business checking statement Deposits $15,000 Business expenses $12,500 Service charges $25",
            "Investment account statement Portfolio value Securities transactions Dividends Market value",
            "Money market account Statement date Balance Minimum balance Interest rate Annual percentage yield",
            "Student loan statement Principal balance Interest accrued Monthly payment Payoff date"
        ]
        
        # Other documents training data
        other_texts = [
            "Research paper Abstract methodology Results conclusions References bibliography",
            "Meeting minutes Attendees agenda items Action items Next meeting scheduled",
            "User manual Installation instructions Configuration Settings troubleshooting Support contact",
            "Policy document Company procedures Guidelines compliance Training requirements",
            "Technical specification Requirements architecture Design implementation Testing",
            "Marketing brochure Product features Benefits customer testimonials Contact information",
            "Press release Company announcement News media Distribution Public relations",
            "Training materials Course outline Learning objectives Exercises Assessment criteria",
            "Incident report Date time Location Description Witnesses Actions taken Follow-up",
            "Performance review Employee evaluation Goals achievements Areas improvement Development plan"
        ]
        
        # Combine all training data
        texts = (invoice_texts + resume_texts + contract_texts + 
                bank_statement_texts + other_texts)
        labels = (['Invoice'] * len(invoice_texts) + 
                 ['Resume'] * len(resume_texts) + 
                 ['Contract'] * len(contract_texts) + 
                 ['Bank Statement'] * len(bank_statement_texts) + 
                 ['Other'] * len(other_texts))
        
        return texts, labels
    
    def train_model(self, texts: List[str] = None, labels: List[str] = None):
        """Train the ML classifier"""
        try:
            if texts is None or labels is None:
                logger.info("Creating synthetic training data...")
                texts, labels = self.create_training_data()
            
            logger.info(f"Training ML classifier with {len(texts)} samples")
            
            # Create pipeline with TF-IDF and Random Forest
            self.pipeline = Pipeline([
                ('tfidf', TfidfVectorizer(
                    max_features=5000,
                    stop_words='english',
                    ngram_range=(1, 2),
                    min_df=2
                )),
                ('classifier', RandomForestClassifier(
                    n_estimators=100,
                    random_state=42,
                    class_weight='balanced'
                ))
            ])
            
            # Split data for validation
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=0.2, random_state=42, stratify=labels
            )
            
            # Train the model
            self.pipeline.fit(X_train, y_train)
            
            # Evaluate on test set
            y_pred = self.pipeline.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            logger.info(f"ML classifier trained with accuracy: {accuracy:.3f}")
            logger.info(f"Classification report:\n{classification_report(y_test, y_pred)}")
            
            self.is_trained = True
            self.save_model()
            
        except Exception as e:
            logger.error(f"Error training ML classifier: {str(e)}")
            self.is_trained = False
    
    def predict(self, text: str) -> Dict[str, any]:
        """Predict document type using ML model"""
        try:
            if not self.is_trained:
                logger.info("Model not trained, training now...")
                self.train_model()
            
            if not self.pipeline:
                raise Exception("No trained model available")
            
            # Get prediction and probabilities
            pred_proba = self.pipeline.predict_proba([text])[0]
            predicted_class = self.pipeline.predict([text])[0]
            confidence = max(pred_proba)
            
            # Get feature importance for interpretation
            feature_names = self.pipeline.named_steps['tfidf'].get_feature_names_out()
            feature_scores = self.pipeline.named_steps['tfidf'].transform([text]).toarray()[0]
            top_features = np.argsort(feature_scores)[-10:][::-1]
            important_features = [feature_names[i] for i in top_features if feature_scores[i] > 0]
            
            return {
                'type': predicted_class,
                'confidence': float(confidence),
                'probabilities': dict(zip(self.pipeline.classes_, pred_proba.tolist())),
                'important_features': important_features[:5],
                'method': 'machine_learning'
            }
            
        except Exception as e:
            logger.error(f"ML prediction error: {str(e)}")
            return {
                'type': 'Other',
                'confidence': 0.0,
                'probabilities': {},
                'important_features': [],
                'method': 'machine_learning',
                'error': str(e)
            }
    
    def retrain_with_feedback(self, text: str, correct_label: str):
        """Retrain model with user feedback (incremental learning simulation)"""
        try:
            # For now, we'll just log the feedback and suggest periodic retraining
            # In a production system, you might implement online learning
            logger.info(f"Received feedback: '{text[:50]}...' should be classified as '{correct_label}'")
            
            # You could store this feedback and periodically retrain
            feedback_file = "models/user_feedback.txt"
            os.makedirs(os.path.dirname(feedback_file), exist_ok=True)
            
            with open(feedback_file, "a", encoding="utf-8") as f:
                f.write(f"{correct_label}\t{text}\n")
            
            logger.info("Feedback saved for future retraining")
            
        except Exception as e:
            logger.error(f"Error saving feedback: {str(e)}")
    
    def get_model_info(self) -> Dict[str, any]:
        """Get information about the trained model"""
        if not self.is_trained or not self.pipeline:
            return {
                'is_trained': False,
                'model_type': 'ML Classifier (TF-IDF + Random Forest)',
                'status': 'Not trained'
            }
        
        try:
            rf_classifier = self.pipeline.named_steps['classifier']
            tfidf = self.pipeline.named_steps['tfidf']
            
            return {
                'is_trained': True,
                'model_type': 'ML Classifier (TF-IDF + Random Forest)',
                'n_estimators': rf_classifier.n_estimators,
                'feature_count': len(tfidf.get_feature_names_out()),
                'classes': list(self.pipeline.classes_),
                'model_path': self.model_path
            }
        except Exception as e:
            logger.error(f"Error getting model info: {str(e)}")
            return {
                'is_trained': self.is_trained,
                'model_type': 'ML Classifier (TF-IDF + Random Forest)',
                'error': str(e)
            }

# Global ML classifier instance
ml_classifier = MLDocumentClassifier()