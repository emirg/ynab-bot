import os
import json
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from domain.repositories.learning_repository import LearningRepository
from domain.models.expense import Expense
from domain.exceptions import LearningDataException

logger = logging.getLogger(__name__)

_MAX_RECENT_TRANSACTIONS = 20

# Pre-built normalization lookup: variant -> canonical name
_PAYEE_NORMALIZATIONS: Dict[str, str] = {}
_NORMALIZATION_RULES = {
    "mcdonalds": ["mcdonald's", "mc donald's", "mc donalds"],
    "home burguer": ["home burger", "homeburger", "home-burger"],
    "exito": ["éxito", "almacenes éxito", "almacenes exito"],
    "carulla": ["carulla fresh market", "supermercados carulla"],
    "olimpica": ["olímpica", "supermercados olimpica", "supermercados olímpica"],
    "falabella": ["saga falabella", "tiendas falabella"],
    "uber": ["uber technologies", "uber trip"],
    "netflix": ["netflix.com", "netflix inc"],
    "spotify": ["spotify premium", "spotify music"]
}
for _canonical, _variants in _NORMALIZATION_RULES.items():
    for _variant in _variants:
        _PAYEE_NORMALIZATIONS[_variant] = _canonical


class JSONLearningRepository(LearningRepository):
    """JSON file implementation of LearningRepository"""
    
    def __init__(self, data_file_path: str):
        self.data_file = data_file_path
        self.learning_data = {
            "payee_category_mapping": {},  # payee -> {category_id: count}
            "category_confidence": {},     # payee -> confidence score
            "last_updated": {},            # payee -> timestamp
            "user_corrections": [],        # Lista de correcciones manuales
            "recent_transactions": [],     # Últimas transacciones para corrección
            "statistics": {
                "total_transactions": 0,
                "learned_associations": 0,
                "accuracy_improvements": 0
            }
        }
        self._ensure_data_file_exists()
        self._load_data()
    
    def _ensure_data_file_exists(self):
        """Ensure data directory and file exist"""
        try:
            data_dir = os.path.dirname(self.data_file)
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
                logger.info(f"Created data directory: {data_dir}")
            
            if not os.path.exists(self.data_file):
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(self.learning_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Created learning data file: {self.data_file}")
        except Exception as e:
            logger.error(f"Failed to create data structure: {e}")
            raise LearningDataException(f"Failed to initialize learning data: {e}")
    
    def _load_data(self):
        """Load learning data from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                
                if 'payee_category_mapping' in loaded_data:
                    self.learning_data = loaded_data
                    associations_count = len(self.learning_data['payee_category_mapping'])
                    if associations_count > 0:
                        logger.info(f"Learning data loaded: {associations_count} associations")
                    else:
                        logger.info("Learning data file loaded (empty, ready to learn)")
                else:
                    logger.warning("Learning data file has incorrect structure, reinitializing")
                    self._save_data()
        except json.JSONDecodeError as e:
            logger.error(f"JSON format error in learning data: {e}")
            logger.info("Reinitializing file with correct structure")
            self._save_data()
        except Exception as e:
            logger.error(f"Error loading learning data: {e}")
            logger.info("Using default data")
    
    def _save_data(self):
        """Save learning data to file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.learning_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")
            raise LearningDataException(f"Failed to save learning data: {e}")
    
    def _normalize_payee(self, payee: str) -> str:
        """Normalize payee name for consistency"""
        if not payee:
            return "unknown"

        normalized = payee.lower().strip()
        normalized = normalized.replace("'", "").replace('"', "")
        normalized = normalized.replace(".", "").replace(",", "")

        # O(1) lookup for exact variant matches
        if normalized in _PAYEE_NORMALIZATIONS:
            return _PAYEE_NORMALIZATIONS[normalized]

        # Substring match for partial variants (e.g. "uber technologies inc")
        for variant, canonical in _PAYEE_NORMALIZATIONS.items():
            if variant in normalized:
                return canonical

        return normalized
    
    def record_successful_transaction(self, expense: Expense) -> None:
        """Record a successful transaction for learning"""
        if not expense.payee or not expense.category_id:
            return
        
        normalized_payee = self._normalize_payee(expense.payee)
        
        # Update mapping
        if normalized_payee not in self.learning_data["payee_category_mapping"]:
            self.learning_data["payee_category_mapping"][normalized_payee] = {}
        
        category_counts = self.learning_data["payee_category_mapping"][normalized_payee]
        category_counts[expense.category_id] = category_counts.get(expense.category_id, 0) + 1
        
        # Update confidence
        total_transactions = sum(category_counts.values())
        max_count = max(category_counts.values())
        confidence = max_count / total_transactions
        self.learning_data["category_confidence"][normalized_payee] = confidence
        
        # Update timestamp
        self.learning_data["last_updated"][normalized_payee] = datetime.now().isoformat()
        
        # Update statistics
        self.learning_data["statistics"]["total_transactions"] += 1
        if normalized_payee not in self.learning_data["payee_category_mapping"] or len(category_counts) == 1:
            self.learning_data["statistics"]["learned_associations"] += 1
        
        self._save_data()
        logger.info(f"Learned association: {normalized_payee} -> {expense.category_name} (confidence: {confidence:.2f})")
    
    def predict_category(self, payee: str, categories: List[Dict]) -> Optional[Tuple[str, float]]:
        """Predict category for a payee, return (category_id, confidence)"""
        if not payee:
            return None
        
        normalized_payee = self._normalize_payee(payee)
        
        if normalized_payee not in self.learning_data["payee_category_mapping"]:
            return None
        
        category_counts = self.learning_data["payee_category_mapping"][normalized_payee]
        if not category_counts:
            return None
        
        # Find most frequent category
        best_category_id = max(category_counts.keys(), key=lambda k: category_counts[k])
        confidence = self.learning_data["category_confidence"].get(normalized_payee, 0.0)
        
        # Verify category still exists in YNAB
        category_ids = {cat.get('id') for cat in categories if cat.get('id')}
        if best_category_id not in category_ids:
            logger.warning(f"Learned category {best_category_id} no longer exists in YNAB")
            return None
        
        logger.info(f"Predicted category for '{payee}': {best_category_id} (confidence: {confidence:.2f})")
        return best_category_id, confidence
    
    def record_user_correction(self, payee: str, old_category_id: str, new_category_id: str) -> None:
        """Record a user correction for learning improvement"""
        normalized_payee = self._normalize_payee(payee)
        
        correction = {
            "payee": normalized_payee,
            "old_category_id": old_category_id,
            "new_category_id": new_category_id,
            "timestamp": datetime.now().isoformat()
        }
        
        self.learning_data["user_corrections"].append(correction)
        
        # Update the mapping with the correction
        if normalized_payee not in self.learning_data["payee_category_mapping"]:
            self.learning_data["payee_category_mapping"][normalized_payee] = {}
        
        # Reduce old category count
        if old_category_id in self.learning_data["payee_category_mapping"][normalized_payee]:
            old_count = self.learning_data["payee_category_mapping"][normalized_payee][old_category_id]
            if old_count <= 1:
                del self.learning_data["payee_category_mapping"][normalized_payee][old_category_id]
            else:
                self.learning_data["payee_category_mapping"][normalized_payee][old_category_id] = old_count - 1
        
        # Increase new category count
        category_counts = self.learning_data["payee_category_mapping"][normalized_payee]
        category_counts[new_category_id] = category_counts.get(new_category_id, 0) + 1
        
        # Recalculate confidence
        total_transactions = sum(category_counts.values())
        max_count = max(category_counts.values()) if category_counts else 0
        confidence = max_count / total_transactions if total_transactions > 0 else 0.0
        self.learning_data["category_confidence"][normalized_payee] = confidence
        
        # Update statistics
        self.learning_data["statistics"]["accuracy_improvements"] += 1
        
        self._save_data()
        logger.info(f"Recorded correction: {normalized_payee} {old_category_id} -> {new_category_id}")
    
    def get_learning_statistics(self) -> Dict:
        """Get learning system statistics"""
        stats = self.learning_data["statistics"].copy()
        stats["learned_payees"] = len(self.learning_data["payee_category_mapping"])
        stats["total_corrections"] = len(self.learning_data["user_corrections"])
        return stats
    
    def add_recent_transaction(self, expense: Expense) -> None:
        """Add transaction to recent transactions for correction purposes"""
        transaction = {
            "payee": expense.payee,
            "amount": float(expense.amount),
            "category_id": expense.category_id,
            "category_name": expense.category_name,
            "timestamp": expense.date.isoformat(),
            "confidence": expense.confidence,
            "parser_source": expense.parser_source
        }

        recent = self.learning_data["recent_transactions"]
        recent.insert(0, transaction)

        # Trim excess entries efficiently
        del recent[_MAX_RECENT_TRANSACTIONS:]

        self._save_data()
    
    def get_recent_transactions(self, limit: int = 10) -> List[Dict]:
        """Get recent transactions for correction purposes"""
        return self.learning_data["recent_transactions"][:limit]