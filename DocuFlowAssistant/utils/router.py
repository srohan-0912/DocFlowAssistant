import os
import shutil
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Department routing configuration
ROUTING_CONFIG = {
    'Invoice': {
        'department': 'Accounting',
        'folder': 'accounting',
        'description': 'Routed to Accounting department for payment processing'
    },
    'Resume': {
        'department': 'Human Resources',
        'folder': 'hr',
        'description': 'Routed to HR department for candidate review'
    },
    'Contract': {
        'department': 'Legal',
        'folder': 'legal',
        'description': 'Routed to Legal department for review and filing'
    },
    'Bank Statement': {
        'department': 'Finance',
        'folder': 'finance',
        'description': 'Routed to Finance department for reconciliation'
    },
    'Other': {
        'department': 'General Office',
        'folder': 'general',
        'description': 'Routed to General Office for manual classification'
    }
}

def route_document(file_path: str, document_type: str, routed_folder: str, department_override: str = None) -> Dict[str, str]:
    """
    Route document to appropriate department folder.
    
    Args:
        file_path: Path to the original document
        document_type: Classification result
        routed_folder: Base folder for routed documents
        department_override: Optional override for department name
        
    Returns:
        Dictionary containing routing information
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")

        # ✅ Use override department if available
        if department_override:
            # Reverse lookup: find matching config for the override
            for config in ROUTING_CONFIG.values():
                if config['department'].lower() == department_override.lower():
                    routing_info = config
                    break
            else:
                routing_info = ROUTING_CONFIG['Other']
        else:
            routing_info = ROUTING_CONFIG.get(document_type, ROUTING_CONFIG['Other'])

        # ✅ Create department folder
        department_folder = os.path.join(routed_folder, routing_info['folder'])
        os.makedirs(department_folder, exist_ok=True)

        # ✅ Handle file naming
        filename = os.path.basename(file_path)
        destination_path = os.path.join(department_folder, filename)
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(destination_path):
            new_filename = f"{base_name}_{counter}{ext}"
            destination_path = os.path.join(department_folder, new_filename)
            counter += 1

        # ✅ Copy file
        shutil.copy2(file_path, destination_path)
        logger.info(f"Document routed: {file_path} -> {destination_path}")

        return {
            'success': True,
            'department': routing_info['department'],
            'folder': routing_info['folder'],
            'path': destination_path,
            'description': routing_info['description'],
            'original_path': file_path
        }

    except Exception as e:
        logger.error(f"Routing failed for {file_path}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'department': 'Error',
            'folder': 'error',
            'path': '',
            'description': f'Routing failed: {str(e)}'
        }

def get_routing_options() -> Dict[str, Dict[str, str]]:
    """Get available routing options."""
    return ROUTING_CONFIG

def update_routing_config(document_type: str, department: str, folder: str, description: str):
    """Update routing configuration for a document type."""
    ROUTING_CONFIG[document_type] = {
        'department': department,
        'folder': folder,
        'description': description
    }
    logger.info(f"Updated routing config for {document_type}")

def simulate_department_action(document_type: str, file_path: str) -> Dict[str, str]:
    """Simulate what each department would do with the document."""
    actions = {
        'Invoice': {
            'action': 'Process Payment',
            'next_steps': ['Verify vendor', 'Check approval', 'Schedule payment'],
            'estimated_time': '2-3 business days'
        },
        'Resume': {
            'action': 'Review Candidate',
            'next_steps': ['Screen qualifications', 'Schedule interview', 'Background check'],
            'estimated_time': '1-2 weeks'
        },
        'Contract': {
            'action': 'Legal Review',
            'next_steps': ['Review terms', 'Check compliance', 'Get signatures'],
            'estimated_time': '3-5 business days'
        },
        'Bank Statement': {
            'action': 'Reconcile Accounts',
            'next_steps': ['Match transactions', 'Verify balances', 'Generate reports'],
            'estimated_time': '1 business day'
        },
        'Other': {
            'action': 'Manual Classification',
            'next_steps': ['Review content', 'Determine type', 'Re-route'],
            'estimated_time': '1-2 business days'
        }
    }
    
    return actions.get(document_type, actions['Other'])
