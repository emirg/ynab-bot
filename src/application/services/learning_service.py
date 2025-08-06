import logging
from typing import Dict, List

from domain.repositories.learning_repository import LearningRepository

logger = logging.getLogger(__name__)


class LearningService:
    """Service for managing learning system and statistics"""
    
    def __init__(self, learning_repository: LearningRepository):
        self.learning_repository = learning_repository
    
    def get_learning_statistics(self) -> Dict:
        """Get comprehensive learning system statistics"""
        try:
            stats = self.learning_repository.get_learning_statistics()
            
            # Add calculated metrics
            if stats.get('total_transactions', 0) > 0:
                stats['accuracy_rate'] = (
                    stats.get('learned_associations', 0) / stats['total_transactions']
                ) * 100
            else:
                stats['accuracy_rate'] = 0.0
            
            if stats.get('learned_associations', 0) > 0:
                stats['correction_rate'] = (
                    stats.get('accuracy_improvements', 0) / stats['learned_associations']
                ) * 100
            else:
                stats['correction_rate'] = 0.0
            
            logger.info(f"Retrieved learning statistics: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get learning statistics: {e}")
            return {
                "error": "No se pudieron obtener las estadísticas",
                "total_transactions": 0,
                "learned_payees": 0,
                "total_corrections": 0,
                "accuracy_rate": 0.0,
                "correction_rate": 0.0
            }
    
    def get_recent_transactions(self, limit: int = 10) -> List[Dict]:
        """Get recent transactions for correction purposes"""
        try:
            transactions = self.learning_repository.get_recent_transactions(limit)
            logger.info(f"Retrieved {len(transactions)} recent transactions")
            return transactions
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {e}")
            return []
    
    def format_statistics_message(self) -> str:
        """Format learning statistics into a user-friendly message"""
        stats = self.get_learning_statistics()
        
        if "error" in stats:
            return f"❌ {stats['error']}"
        
        message = f"""
📊 *Estadísticas del Sistema de Aprendizaje*

🔢 *Transacciones totales:* {stats.get('total_transactions', 0)}
🏪 *Comercios aprendidos:* {stats.get('learned_payees', 0)}
📈 *Asociaciones exitosas:* {stats.get('learned_associations', 0)}
🔄 *Correcciones del usuario:* {stats.get('total_corrections', 0)}

📊 *Métricas:*
• *Tasa de aprendizaje:* {stats.get('accuracy_rate', 0):.1f}%
• *Tasa de corrección:* {stats.get('correction_rate', 0):.1f}%

💡 *Estado del sistema:* {"🟢 Activo" if stats.get('total_transactions', 0) > 0 else "🟡 Iniciando"}
        """
        
        return message.strip()
    
    def format_recent_transactions_message(self, limit: int = 5) -> str:
        """Format recent transactions into a user-friendly message"""
        transactions = self.get_recent_transactions(limit)
        
        if not transactions:
            return "📋 No hay transacciones recientes registradas."
        
        message = f"📋 *Últimas {len(transactions)} transacciones:*\n\n"
        
        for i, transaction in enumerate(transactions):
            payee = transaction.get('payee', 'Desconocido')
            amount = transaction.get('amount', 0)
            category_name = transaction.get('category_name', 'Sin categoría')
            confidence = transaction.get('confidence', 0) * 100
            parser_source = transaction.get('parser_source', 'unknown')
            
            source_emoji = {
                'llm': '🤖',
                'learning': '🧠',
                'manual': '👤'
            }.get(parser_source, '❓')
            
            message += f"{i+1}. *{payee}* - ${amount:,.0f}\n"
            message += f"   📁 {category_name} {source_emoji} ({confidence:.0f}% confianza)\n\n"
        
        message += "💡 Usa `/corregir <número>` para corregir una categoría"
        
        return message