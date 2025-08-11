import logging
from typing import Dict, List, Tuple
from utils.classifier import classify_document as rule_based_classify
from utils.ml_classifier import ml_classifier
from utils.ocr_extractor import clean_text

logger = logging.getLogger(__name__)

class HybridDocumentClassifier:
    """
    Advanced hybrid document classifier combining multiple approaches:
    1. Rule-based classification (keyword and pattern matching)
    2. Machine learning classification (TF-IDF + Random Forest)
    3. Confidence weighting and ensemble decision making
    
    This demonstrates the complete document classification pipeline:
    Text Input → Feature Extraction → Multiple Classifiers → Ensemble Decision → Final Classification
    """
    
    def __init__(self):
        self.confidence_threshold = 0.7
        self.ml_weight = 0.6  # Weight for ML predictions
        self.rule_weight = 0.4  # Weight for rule-based predictions
        
    def classify_document(self, text: str) -> Dict[str, any]:
        """
        Comprehensive document classification using hybrid approach.
        
        Pipeline:
        1. Text preprocessing and validation
        2. Rule-based classification (keywords, patterns)
        3. ML-based classification (TF-IDF features)
        4. Ensemble decision making
        5. Confidence scoring and validation
        
        Args:
            text: Extracted document text
            
        Returns:
            Classification result with detailed pipeline information
        """
        if not text or not text.strip():
            return {
                'type': 'Other',
                'confidence': 0.0,
                'method': 'hybrid',
                'pipeline_stages': ['input_validation'],
                'error': 'No text content provided',
                'rule_based_result': None,
                'ml_result': None,
                'ensemble_decision': 'failed_validation'
            }
        
        logger.info("Starting hybrid classification pipeline...")
        pipeline_stages = ['input_validation', 'rule_based_analysis']
        
        # Clean the text before classification
        text_cleaned = clean_text(text)
        logger.debug(f"[HYBRID] Cleaned input text preview: {text_cleaned[:300]}")
        
        # Stage 1: Rule-based classification
        logger.debug("Stage 1: Rule-based classification")
        rule_result = rule_based_classify(text)
        
        pipeline_stages.append('ml_analysis')
        
        # Stage 2: Machine learning classification
        logger.debug("Stage 2: ML-based classification")
        ml_result = ml_classifier.predict(text_cleaned)

        pipeline_stages.append('ensemble_decision')

       # Stage 3: Ensemble decision making
        logger.debug("Stage 3: Ensemble decision making")
        final_result = self._ensemble_classify(rule_result, ml_result, text_cleaned)

        
        pipeline_stages.append('confidence_validation')
        
        # Stage 4: Add pipeline metadata
        final_result.update({
            'pipeline_stages': pipeline_stages,
            'rule_based_result': rule_result,
            'ml_result': ml_result,
            'ensemble_weights': {
                'ml_weight': self.ml_weight,
                'rule_weight': self.rule_weight
            }
        })
        
        logger.info(f"Classification complete: {final_result['type']} (confidence: {final_result['confidence']:.2f})")
        return final_result
    
    def _ensemble_classify(self, rule_result: Dict, ml_result: Dict, text: str) -> Dict[str, any]:
        """
        Ensemble classification combining rule-based and ML predictions.
        
        Decision Logic:
        1. If both methods agree with high confidence → Use agreed result
        2. If methods disagree → Use weighted average confidence
        3. If one method has very low confidence → Trust the other
        4. Fallback to highest confidence prediction
        """
        rule_type = rule_result.get('type', 'Other')
        rule_confidence = rule_result.get('confidence', 0.0)
        
        ml_type = ml_result.get('type', 'Other')
        ml_confidence = ml_result.get('confidence', 0.0)
        
        # Case 1: Both methods agree
        if rule_type == ml_type:
            # Use weighted average confidence when methods agree
            combined_confidence = (rule_confidence * self.rule_weight + 
                                 ml_confidence * self.ml_weight)
            
            return {
                'type': rule_type,
                'confidence': min(combined_confidence, 1.0),
                'method': 'hybrid_agreement',
                'ensemble_decision': 'agreement',
                'decision_factors': [
                    f"Both methods classified as {rule_type}",
                    f"Rule confidence: {rule_confidence:.2f}",
                    f"ML confidence: {ml_confidence:.2f}",
                    f"Combined confidence: {combined_confidence:.2f}"
                ]
            }
        
        # Case 2: High confidence from one method, low from other
        if ml_confidence >= self.confidence_threshold and rule_confidence < 0.5:
            return {
                'type': ml_type,
                'confidence': ml_confidence,
                'method': 'hybrid_ml_dominant',
                'ensemble_decision': 'ml_override',
                'decision_factors': [
                    f"ML high confidence ({ml_confidence:.2f}) vs rule low confidence ({rule_confidence:.2f})",
                    f"Trusting ML classification: {ml_type}"
                ]
            }
        
        if rule_confidence >= self.confidence_threshold and ml_confidence < 0.5:
            return {
                'type': rule_type,
                'confidence': rule_confidence,
                'method': 'hybrid_rule_dominant',
                'ensemble_decision': 'rule_override',
                'decision_factors': [
                    f"Rule high confidence ({rule_confidence:.2f}) vs ML low confidence ({ml_confidence:.2f})",
                    f"Trusting rule-based classification: {rule_type}"
                ]
            }
        
        # Case 3: Methods disagree with similar confidence
        # Use the method with higher confidence, but reduce overall confidence
        if ml_confidence > rule_confidence:
            confidence_penalty = 0.2  # Reduce confidence due to disagreement
            final_confidence = max(ml_confidence - confidence_penalty, 0.3)
            
            return {
                'type': ml_type,
                'confidence': final_confidence,
                'method': 'hybrid_ml_preferred',
                'ensemble_decision': 'disagreement_ml_wins',
                'decision_factors': [
                    f"Methods disagree: ML={ml_type}({ml_confidence:.2f}) vs Rule={rule_type}({rule_confidence:.2f})",
                    f"Selecting ML result with reduced confidence",
                    f"Confidence penalty applied: -{confidence_penalty}"
                ]
            }
        else:
            confidence_penalty = 0.2
            final_confidence = max(rule_confidence - confidence_penalty, 0.3)
            
            return {
                'type': rule_type,
                'confidence': final_confidence,
                'method': 'hybrid_rule_preferred',
                'ensemble_decision': 'disagreement_rule_wins',
                'decision_factors': [
                    f"Methods disagree: Rule={rule_type}({rule_confidence:.2f}) vs ML={ml_type}({ml_confidence:.2f})",
                    f"Selecting rule-based result with reduced confidence",
                    f"Confidence penalty applied: -{confidence_penalty}"
                ]
            }
    
    def get_classification_explanation(self, result: Dict) -> str:
        """Generate human-readable explanation of classification decision."""
        decision_type = result.get('ensemble_decision', 'unknown')
        doc_type = result.get('type', 'Unknown')
        confidence = result.get('confidence', 0.0)
        
        explanations = {
            'agreement': f"Both rule-based and ML methods agreed on '{doc_type}' with combined confidence of {confidence:.1%}",
            'ml_override': f"ML method had high confidence ({confidence:.1%}) for '{doc_type}', overriding rule-based result",
            'rule_override': f"Rule-based method had high confidence ({confidence:.1%}) for '{doc_type}', overriding ML result",
            'disagreement_ml_wins': f"Methods disagreed, but ML confidence was higher for '{doc_type}' ({confidence:.1%})",
            'disagreement_rule_wins': f"Methods disagreed, but rule-based confidence was higher for '{doc_type}' ({confidence:.1%})",
            'failed_validation': "Classification failed due to insufficient input text"
        }
        
        return explanations.get(decision_type, f"Classified as '{doc_type}' with {confidence:.1%} confidence")

# Global hybrid classifier instance
hybrid_classifier = HybridDocumentClassifier()

class HybridClassifier:
    """Hybrid classifier that combines rule-based and ML approaches"""
    
    def __init__(self):
        self.rule_weight = 0.3
        self.ml_weight = 0.7
        self.confidence_threshold = 0.6
    
    def classify_document(self, text: str) -> Dict[str, any]:
        """
        Classify document using both rule-based and ML approaches,
        then combine results intelligently.
        """
        try:
            # Get predictions from both methods
            text_cleaned = clean_text(text)
            rule_result = rule_based_classify(text)  # keep rule-based on raw
            ml_result = ml_classifier.predict(text_cleaned)  # ML on cleaned

            
            # Handle ML prediction errors
            if 'error' in ml_result:
                logger.warning(f"ML classifier error: {ml_result['error']}")
                return {
                    **rule_result,
                    'method': 'rule_based_fallback',
                    'ml_error': ml_result['error']
                }
            
            # Combine predictions based on confidence and agreement
            final_result = self._combine_predictions(rule_result, ml_result, text)
            
            return final_result
            
        except Exception as e:
            logger.error(f"Hybrid classification error: {str(e)}")
            # Fallback to rule-based classification
            rule_result = rule_based_classify(text)
            return {
                **rule_result,
                'method': 'rule_based_fallback',
                'error': str(e)
            }
    
    def _combine_predictions(self, rule_result: Dict, ml_result: Dict, text: str) -> Dict[str, any]:
        """Intelligently combine rule-based and ML predictions"""
        
        rule_type = rule_result['type']
        ml_type = ml_result['type']
        rule_confidence = rule_result['confidence']
        ml_confidence = ml_result['confidence']
        
        # Case 1: Both methods agree
        if rule_type == ml_type:
            # Use weighted average of confidences
            combined_confidence = (rule_confidence * self.rule_weight + 
                                 ml_confidence * self.ml_weight)
            
            return {
                'type': rule_type,
                'confidence': combined_confidence,
                'method': 'hybrid_agreement',
                'rule_result': rule_result,
                'ml_result': ml_result,
                'reasoning': f"Both methods agree on '{rule_type}'"
            }
        
        # Case 2: Methods disagree - use confidence and specific logic
        else:
            # If ML has high confidence and rule-based has low confidence
            if ml_confidence > 0.8 and rule_confidence < 0.4:
                return {
                    'type': ml_type,
                    'confidence': ml_confidence,
                    'method': 'ml_dominant',
                    'rule_result': rule_result,
                    'ml_result': ml_result,
                    'reasoning': f"ML high confidence ({ml_confidence:.2f}) vs rule low confidence ({rule_confidence:.2f})"
                }
            
            # If rule-based has high confidence and ML has low confidence
            elif rule_confidence > 0.7 and ml_confidence < 0.5:
                return {
                    'type': rule_type,
                    'confidence': rule_confidence,
                    'method': 'rule_dominant',
                    'rule_result': rule_result,
                    'ml_result': ml_result,
                    'reasoning': f"Rule high confidence ({rule_confidence:.2f}) vs ML low confidence ({ml_confidence:.2f})"
                }
            
            # If both have moderate confidence, check for specific patterns
            else:
                final_type, final_confidence, reasoning = self._resolve_disagreement(
                    rule_result, ml_result, text
                )
                
                return {
                    'type': final_type,
                    'confidence': final_confidence,
                    'method': 'hybrid_resolved',
                    'rule_result': rule_result,
                    'ml_result': ml_result,
                    'reasoning': reasoning
                }
    
    def _resolve_disagreement(self, rule_result: Dict, ml_result: Dict, text: str) -> tuple:
        """Resolve disagreements between rule-based and ML predictions"""
        
        rule_type = rule_result['type']
        ml_type = ml_result['type']
        rule_confidence = rule_result['confidence']
        ml_confidence = ml_result['confidence']
        
        # Check for specific document indicators
        text_lower = text.lower()
        
        # Strong indicators for specific document types
        strong_invoice_indicators = ['invoice number', 'amount due', 'payment terms', 'bill to']
        strong_resume_indicators = ['experience', 'education', 'skills', 'employment history']
        strong_contract_indicators = ['agreement', 'whereas', 'terms and conditions', 'parties']
        strong_bank_indicators = ['account number', 'balance', 'statement period', 'transaction']
        
        # Count strong indicators
        invoice_score = sum(1 for indicator in strong_invoice_indicators if indicator in text_lower)
        resume_score = sum(1 for indicator in strong_resume_indicators if indicator in text_lower)
        contract_score = sum(1 for indicator in strong_contract_indicators if indicator in text_lower)
        bank_score = sum(1 for indicator in strong_bank_indicators if indicator in text_lower)
        
        # Determine which type has strongest indicators
        indicator_scores = {
            'Invoice': invoice_score,
            'Resume': resume_score,
            'Contract': contract_score,
            'Bank Statement': bank_score
        }
        
        max_indicator_type = max(indicator_scores.keys(), key=lambda k: indicator_scores[k])
        max_indicator_score = indicator_scores[max_indicator_type]
        
        # If strong indicators exist, use them to guide decision
        if max_indicator_score >= 2:
            # Choose the prediction that matches strong indicators
            if rule_type == max_indicator_type:
                return rule_type, rule_confidence * 1.1, f"Rule-based matches strong indicators for {max_indicator_type}"
            elif ml_type == max_indicator_type:
                return ml_type, ml_confidence * 1.1, f"ML matches strong indicators for {max_indicator_type}"
        
        # If no strong indicators, use weighted combination based on historical accuracy
        # For now, slightly favor ML as it can learn patterns
        if ml_confidence > rule_confidence:
            return ml_type, ml_confidence, f"ML slightly more confident ({ml_confidence:.2f} vs {rule_confidence:.2f})"
        else:
            return rule_type, rule_confidence, f"Rule-based slightly more confident ({rule_confidence:.2f} vs {ml_confidence:.2f})"
    
    def get_classifier_info(self) -> Dict[str, any]:
        """Get information about both classifiers"""
        return {
            'rule_based': {
                'method': 'keyword_pattern_matching',
                'weight': self.rule_weight
            },
            'machine_learning': ml_classifier.get_model_info(),
            'hybrid': {
                'rule_weight': self.rule_weight,
                'ml_weight': self.ml_weight,
                'confidence_threshold': self.confidence_threshold
            }
        }
    
    def update_weights(self, rule_weight: float, ml_weight: float):
        """Update the weights for combining predictions"""
        total = rule_weight + ml_weight
        self.rule_weight = rule_weight / total
        self.ml_weight = ml_weight / total
        logger.info(f"Updated classifier weights: rule={self.rule_weight:.2f}, ml={self.ml_weight:.2f}")

# Global hybrid classifier instance
hybrid_classifier = HybridClassifier()