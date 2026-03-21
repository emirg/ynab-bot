import logging
from typing import Dict, List

from domain.repositories.learning_repository import LearningRepository

logger = logging.getLogger(__name__)


class LearningService:
    """Service for managing learning system and statistics"""

    def __init__(self, learning_repository: LearningRepository):
        self.learning_repository = learning_repository

    def get_learning_statistics(self, telegram_id: int) -> Dict:
        """Get comprehensive learning system statistics"""
        try:
            stats = self.learning_repository.get_learning_statistics(telegram_id)

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

    def get_recent_transactions(self, telegram_id: int, limit: int = 10) -> List[Dict]:
        """Get recent transactions for correction purposes"""
        try:
            transactions = self.learning_repository.get_recent_transactions(telegram_id, limit)
            logger.info(f"Retrieved {len(transactions)} recent transactions")
            return transactions
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {e}")
            return []

    def format_statistics_message(self, telegram_id: int) -> str:
        """Format learning statistics into a user-friendly message"""
        stats = self.get_learning_statistics(telegram_id)

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
"""

        # Add top payees
        top_payees = self._get_top_payees(telegram_id, 3)
        if top_payees:
            message += "\n🏪 *Comercios más frecuentes:*\n"
            for p in top_payees:
                payee = p.get("normalized_payee", "Desconocido").title()
                count = p.get("count", 0)
                message += f"• {payee} ({count} {'vez' if count == 1 else 'veces'})\n"

        # Add top categories
        top_categories = self._get_top_categories(telegram_id, 3)
        if top_categories:
            message += "\n📁 *Categorías más usadas:*\n"
            for c in top_categories:
                name = c.get("name", "Desconocida")
                count = c.get("count", 0)
                message += f"• {name} ({count} txn)\n"

        message += f'\n💡 *Estado del sistema:* {"🟢 Activo" if stats.get("total_transactions", 0) > 0 else "🟡 Iniciando"}'

        return message.strip()

    def get_payee_associations(self, telegram_id: int) -> List[Dict]:
        """Get all payee-category associations for a user"""
        try:
            return self.learning_repository.get_payee_associations(telegram_id)
        except Exception as e:
            logger.error(f"Failed to get payee associations: {e}")
            return []

    def forget_payee(self, telegram_id: int, payee: str) -> bool:
        """Forget all associations for a given payee"""
        try:
            from domain.services.payee_normalizer import normalize_payee

            normalized = normalize_payee(payee)
            deleted_count = self.learning_repository.delete_payee_associations(
                telegram_id, normalized
            )
            if deleted_count > 0:
                logger.info(
                    f"User {telegram_id} forgot payee '{payee}' ({normalized}) - {deleted_count} rows deleted"
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to forget payee '{payee}': {e}")
            return False

    def format_learning_dashboard_message(self, telegram_id: int) -> str:
        """Build the /aprendizaje response message"""
        associations = self.get_payee_associations(telegram_id)

        if not associations:
            return "📔 *Todavía no he aprendido nada sobre tus gastos.*\n\nA medida que registres transacciones, iré aprendiendo a qué categorías pertenecen tus comercios favoritos."

        # Limit to top 20 to avoid message overflow
        top_associations = associations[:20]

        message = "🧠 *Panel de Aprendizaje*\n\n"
        message += "Estos son los comercios que he aprendido a categorizar:\n\n"

        for assoc in top_associations:
            payee = assoc.get("normalized_payee", "Desconocido").title()
            category = assoc.get("category_name") or "Categoría desconocida"
            count = assoc.get("count", 0)

            message += (
                f"• *{payee}* → {category} ({count} {'vez' if count == 1 else 'veces'})\n"
            )

        if len(associations) > 20:
            message += f"\n... y {len(associations) - 20} comercios más."

        message += "\n\n💡 Si me he equivocado con alguno, usa `/olvidar <comercio>` para que borre lo aprendido sobre él."

        return message

    def format_forget_result_message(self, payee: str, success: bool) -> str:
        """Return Spanish success/failure message for /olvidar"""
        if success:
            return f"✅ He olvidado todo lo que sabía sobre *{payee}*. La próxima vez que registres un gasto allí, te preguntaré de nuevo la categoría."
        else:
            return f"❓ No encontré ninguna información guardada sobre *{payee}*."

    def _get_top_payees(self, telegram_id: int, limit: int = 3) -> List[Dict]:
        """Helper to get top frequent payees"""
        associations = self.get_payee_associations(telegram_id)
        # They are already sorted by count DESC from repo
        return associations[:limit]

    def _get_top_categories(self, telegram_id: int, limit: int = 3) -> List[Dict]:
        """Helper to get top frequent categories"""
        associations = self.get_payee_associations(telegram_id)

        # Group by category
        cat_counts = {}
        for assoc in associations:
            cat_id = assoc.get("category_id")
            cat_name = assoc.get("category_name") or "Categoría desconocida"
            count = assoc.get("count", 0)

            if cat_id not in cat_counts:
                cat_counts[cat_id] = {"name": cat_name, "count": 0}
            cat_counts[cat_id]["count"] += count

        # Sort by count
        sorted_cats = sorted(cat_counts.values(), key=lambda x: x["count"], reverse=True)
        return sorted_cats[:limit]

    def format_recent_transactions_message(self, telegram_id: int, limit: int = 5) -> str:
        """Format recent transactions into a user-friendly message"""
        transactions = self.get_recent_transactions(telegram_id, limit)

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
