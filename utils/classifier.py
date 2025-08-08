import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Document type keywords and patterns
CLASSIFICATION_RULES = {
    'Invoice': {
        'keywords': [
            'invoice', 'inv#', 'invoice number', 'invoice date', 'invoice total',
            'bill', 'billing', 'billed to', 'billing address',
            'amount due', 'total due', 'balance due', 'due date', 'payment due',
            'subtotal', 'total amount', 'net total', 'tax', 'gst', 'vat',
            'remit to', 'pay to', 'charge', 'payment terms', 'reference number',
            'purchase order', 'po number', 'service description', 'item', 'quantity', 'unit price'
        ],
        'patterns': [
            r'invoice\s*#?\s*\d+',
            r'invoice\s+number\s*:?\s*\d+',
            r'invoice\s+date\s*:?\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
            r'total\s*amount\s*:?\s*\$?\d+(\.\d{2})?',
            r'amount\s*due\s*:?\s*\$?\d+(\.\d{2})?',
            r'balance\s*due\s*:?\s*\$?\d+(\.\d{2})?',
            r'payment\s*due\s*:?\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
            r'po\s*(number)?\s*:?\s*\d+',
            r'\$\d{1,3}(,\d{3})*(\.\d{2})?'  # Currency format
        ],
        'weight': 1.0
    },
    'Resume': {
    'keywords': [
        'resume', 'curriculum vitae', 'cv',
        'summary', 'objective', 'profile', 'career goal', 'career summary',
        'experience', 'professional experience', 'work experience', 'work history',
        'education', 'academic background', 'qualifications',
        'skills', 'technical skills', 'soft skills', 'languages',
        'certifications', 'projects', 'internship', 'extracurricular',
        'achievements', 'awards', 'publications', 'conference',
        'references', 'referees', 'contact', 'personal information',
        'phone', 'email', 'address', 'linkedin', 'portfolio', 'github', 'website'
    ],
    'patterns': [
        r'curriculum\s+vitae',
        r'education\s*:?',
        r'experience\s*:?',
        r'(professional|work)\s+experience',
        r'skills\s*:?',
        r'certification[s]?\s*:?',
        r'\d{4}\s*[-–]\s*\d{4}',           # Year range (e.g., 2020 - 2024)
        r'\d{4}\s*[-–]\s*present',         # Year to Present
        r'bachelor|master|phd|degree',
        r'university|college|institute|school',
        r'(linkedin|github|portfolio|website)\.com\/[^\s]+'
    ],
    'weight': 1.0
    },
    'Contract': {
    'keywords': [
        'contract', 'agreement', 'terms and conditions', 'terms of service',
        'party', 'parties', 'obligations', 'liabilities', 'representations',
        'warranty', 'warranties', 'hereby', 'hereinafter', 'therein', 'thereof',
        'executed', 'binding', 'witness', 'signature', 'signatory',
        'effective date', 'termination', 'duration', 'renewal',
        'confidentiality', 'non-disclosure', 'nda',
        'breach', 'remedies', 'dispute', 'governing law', 'jurisdiction',
        'force majeure', 'indemnity', 'indemnification', 'clause'
    ],
    'patterns': [
        r'this\s+(agreement|contract)\s+is\s+(made|entered\s+into)',
        r'by\s+and\s+between\s+.*?,\s+and\s+.*?',     # "by and between X and Y"
        r'party\s+of\s+the\s+(first|second)\s+part',
        r'hereby\s+agrees?\s+to',
        r'in\s+witness\s+whereof',
        r'(effective\s+date|date\s+of\s+effect)',
        r'terms?\s+(and|&)\s+conditions',
        r'this\s+contract\s+shall\s+be\s+(governed|construed)',
        r'governed\s+by\s+the\s+laws\s+of',
        r'breach\s+of\s+contract',
        r'non[-\s]?disclosure\s+agreement',
        r'\bnda\b',
        r'confidentiality\s+clause',
        r'termination\s+clause'
    ],
    'weight': 1.0
    },
    'Bank Statement': {
    'keywords': [
        'bank statement', 'account statement', 'statement period',
        'account summary', 'transaction details', 'balance', 'opening balance',
        'closing balance', 'available balance', 'transaction', 'transactions',
        'debit', 'credit', 'deposit', 'withdrawal', 'interest',
        'checking account', 'savings account',
        'account number', 'routing number',
        'bank name', 'branch', 'currency', 'statement date',
        'ledger balance', 'balance forward', 'total debits', 'total credits'
    ],
    'patterns': [
        r'account\s*(number|no\.?)\s*[:\-]?\s*\d{6,}',                 # account number formats
        r'available\s+balance\s*[:\-]?\s*\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
        r'(opening|beginning)\s+balance\s*[:\-]?\s*\$?\d+(\.\d{2})?',
        r'(closing|ending)\s+balance\s*[:\-]?\s*\$?\d+(\.\d{2})?',
        r'statement\s+(period|date|from|to)\s*[:\-]?\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
        r'transaction\s+(date|details)?\s*[:\-]?',
        r'\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?',                       # currency with commas
        r'(debit|credit)\s+[:\-]?\s*\$?\d+(\.\d{2})?',
        r'total\s+(debits|credits)\s*[:\-]?\s*\$?\d+(\.\d{2})?',
        r'bank\s+(name|branch)?\s*[:\-]?\s*[a-zA-Z ]+'
    ],
    'weight': 1.0
    }
}

def classify_document(text: str) -> Dict[str, any]:
    """
    Classify document based on content using keyword matching and pattern recognition.
    
    Args:
        text: Extracted text from document
        
    Returns:
        Dictionary containing classification results
    """
    if not text or not text.strip():
        return {
            'type': 'Other',
            'confidence': 0.0,
            'scores': {},
            'reasoning': 'No text content found'
        }
    
    text_lower = text.lower()
    scores = {}
    reasoning_details = {}
    
    for doc_type, rules in CLASSIFICATION_RULES.items():
        score = calculate_type_score(text_lower, text, rules)
        scores[doc_type] = score
        reasoning_details[doc_type] = get_matching_elements(text_lower, text, rules)
    
    # Find the best match
    best_type = max(scores.keys(), key=lambda k: scores[k])
    best_score = scores[best_type]
    logger.debug(f"[Classifier] Scores: {scores}")
    logger.debug(f"[Classifier] Best match: {best_type} ({round(best_score, 2)})")

    
    # Apply confidence thresholds
    if best_score < 0.3:
        classification_type = 'Other'
        confidence = 0.5  # Low confidence for "Other"
    else:
        classification_type = best_type
        confidence = min(best_score, 1.0)
    
    return {
        'type': classification_type,
        'confidence': round(confidence, 2),
        'scores': {k: round(v, 2) for k, v in scores.items()},
        'reasoning': reasoning_details.get(classification_type, [])
    }

def calculate_type_score(text_lower: str, original_text: str, rules: Dict) -> float:
    """Calculate score for a specific document type."""
    keyword_score = 0
    pattern_score = 0
    
    # Check keywords
    keywords_found = 0
    for keyword in rules['keywords']:
        if keyword.lower() in text_lower:
            keywords_found += 1
    
    if rules['keywords']:
        keyword_score = (keywords_found / len(rules['keywords'])) * 0.7
    
    # Check patterns
    patterns_found = 0
    for pattern in rules.get('patterns', []):
        if re.search(pattern, original_text, re.IGNORECASE):
            patterns_found += 1
    
    if rules.get('patterns'):
        pattern_score = (patterns_found / len(rules['patterns'])) * 0.3
    
    total_score = (keyword_score + pattern_score) * rules.get('weight', 1.0)
    return total_score

def get_matching_elements(text_lower: str, original_text: str, rules: Dict) -> List[str]:
    """Get list of matching keywords and patterns for reasoning."""
    matches = []
    
    # Find matching keywords
    for keyword in rules['keywords']:
        if keyword.lower() in text_lower:
            matches.append(f"Keyword: '{keyword}'")
    
    # Find matching patterns
    for pattern in rules.get('patterns', []):
        match = re.search(pattern, original_text, re.IGNORECASE)
        if match:
            matches.append(f"Pattern: '{match.group()}'")
    
    return matches[:5]  # Return top 5 matches for brevity

def get_document_types() -> List[str]:
    """Get list of available document types."""
    return list(CLASSIFICATION_RULES.keys()) + ['Other']

def update_classification_rules(doc_type: str, keywords: List[str], patterns: List[str] = None):
    """Update classification rules for a document type (for manual tuning)."""
    if patterns is None:
        patterns = []
    
    CLASSIFICATION_RULES[doc_type] = {
        'keywords': keywords,
        'patterns': patterns,
        'weight': 1.0
    }
    
    logger.info(f"Updated classification rules for {doc_type}")
