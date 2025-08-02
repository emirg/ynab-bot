import logging
from typing import Dict, Optional, List
from parsers.llm_expense_parser import LLMExpenseParser
from integrations.ynab_category_manager import YNABCategoryManager
from integrations.ynab_account_manager import YNABAccountManager
from parsers.adaptive_category_learner import AdaptiveCategoryLearner

logger = logging.getLogger(__name__)


class SmartExpenseParser:
    """
    Parser inteligente usando solo LLM para máxima precisión y consistencia
    """
    
    def __init__(self, ynab_client=None):
        # Configuración LLM (requerido)
        self.llm_parser = LLMExpenseParser()
        
        # Inicializar gestor de categorías YNAB
        self.category_manager = None
        if ynab_client:
            self.category_manager = YNABCategoryManager(ynab_client)
        
        # Inicializar gestor de cuentas YNAB
        self.account_manager = None
        if ynab_client:
            self.account_manager = YNABAccountManager(ynab_client)
        
        # Inicializar sistema de aprendizaje adaptativo
        self.adaptive_learner = AdaptiveCategoryLearner()
    
    def load_ynab_categories(self, budget_id: str) -> bool:
        """Carga las categorías y cuentas YNAB y las actualiza en el LLM parser"""
        success = True
        
        # Cargar categorías
        if self.category_manager:
            cat_success = self.category_manager.load_categories(budget_id)
            success = success and cat_success
            
            if cat_success and self.llm_parser:
                categories = self.category_manager.get_categories_list()
                self.llm_parser.update_categories(categories)
                logger.info("Categorías YNAB cargadas y actualizadas en LLM parser")
        
        # Cargar cuentas
        if self.account_manager:
            acc_success = self.account_manager.load_accounts(budget_id)
            success = success and acc_success
            
            if acc_success and self.llm_parser:
                accounts = self.account_manager.get_account_names_for_llm()
                self.llm_parser.update_accounts(accounts)
                logger.info("Cuentas YNAB cargadas y actualizadas en LLM parser")
        
        return success
    
    def parse_expense(self, message: str) -> Optional[Dict]:
        """
        Parsea un mensaje de gasto usando LLM inteligente
        
        Args:
            message: Mensaje del usuario sobre un gasto
            
        Returns:
            Dict con información del gasto o None si falla
        """
        if not self.llm_parser:
            logger.error("LLM parser no está disponible")
            return None
        
        # Parsear con LLM
        logger.info("Parseando mensaje con LLM...")
        result = self.llm_parser.parse_expense(message)
        
        if not result or result.get('confidence', 0) < 0.3:
            logger.warning(f"LLM no pudo parsear el mensaje con suficiente confianza: '{message}'")
            return None
        
        # Marcar como parseado por LLM
        result['parser_used'] = 'llm'
        
        # Mejorar con categorías YNAB reales y aprendizaje adaptativo
        result = self._enhance_with_ynab_category(result, message)
        
        # Procesar detección de cuenta
        result = self._process_account_detection(result, message)
        
        logger.info(f"Parseo exitoso con LLM (confianza: {result.get('confidence', 0):.2f})")
        return result
    
    def _enhance_with_ynab_category(self, result: Dict, original_message: str) -> Dict:
        """Mejora el resultado con categorías YNAB reales y aprendizaje adaptativo"""
        payee = result.get('payee', '')
        
        # Paso 1: Intentar predicción con aprendizaje adaptativo (más preciso)
        if payee and self.adaptive_learner:
            learned_prediction = self.adaptive_learner.predict_category(payee)
            
            if learned_prediction:
                category_id, category_name, learned_confidence = learned_prediction
                
                # Si la predicción aprendida es muy confiable, usarla
                if learned_confidence > 0.8:
                    result['category'] = category_name
                    result['category_id'] = category_id
                    result['learned_confidence'] = learned_confidence
                    result['prediction_source'] = 'adaptive_learning'
                    
                    # Ajustar confianza general
                    original_confidence = result.get('confidence', 0.5)
                    result['confidence'] = min(1.0, original_confidence + (learned_confidence * 0.3))
                    
                    logger.info(f"Categoría predicha por aprendizaje: {payee} → {category_name} "
                               f"(confianza: {learned_confidence:.2f})")
                    return result
        
        # Paso 2: Fallback a búsqueda YNAB tradicional si no hay predicción aprendida
        if not self.category_manager:
            return result
        
        search_text = f"{result.get('category', '')} {payee} {original_message}"
        ynab_category = self.category_manager.find_best_category(search_text)
        
        if ynab_category:
            category_id, category_name, ynab_confidence = ynab_category
            
            # Si la confianza de YNAB es alta, usar esa categoría
            if ynab_confidence > 0.6:
                result['category'] = category_name
                result['category_id'] = category_id
                result['ynab_category_confidence'] = ynab_confidence
                result['prediction_source'] = 'ynab_search'
                
                # Ajustar confianza general
                original_confidence = result.get('confidence', 0.5)
                result['confidence'] = min(1.0, original_confidence + (ynab_confidence * 0.2))
                
                logger.info(f"Categoría encontrada con YNAB: {category_name} (confianza: {ynab_confidence:.2f})")
        
        return result
    
    def _process_account_detection(self, result: Dict, original_message: str) -> Dict:
        """Procesa la detección de cuenta del LLM y la mapea a cuentas YNAB reales"""
        if not self.account_manager:
            return result
        
        # Si el LLM detectó una cuenta, intentar mapearla
        detected_account = result.get('account')
        if detected_account and detected_account != 'null':
            # Buscar la cuenta en YNAB
            account_match = self.account_manager.find_best_account(detected_account)
            
            if account_match:
                account_id, account_name, confidence = account_match
                result['account_id'] = account_id
                result['account_name'] = account_name
                result['account_confidence'] = confidence
                
                logger.info(f"Cuenta detectada y mapeada: {detected_account} → {account_name} "
                           f"(confianza: {confidence:.2f})")
            else:
                # Si no se pudo mapear, buscar directamente en el mensaje original
                fallback_match = self.account_manager.find_best_account(original_message)
                if fallback_match:
                    account_id, account_name, confidence = fallback_match
                    result['account_id'] = account_id
                    result['account_name'] = account_name
                    result['account_confidence'] = confidence
                    
                    logger.info(f"Cuenta detectada por fallback: {account_name} "
                               f"(confianza: {confidence:.2f})")
        else:
            # Si el LLM no detectó cuenta, intentar detección directa en el mensaje
            account_match = self.account_manager.find_best_account(original_message)
            if account_match:
                account_id, account_name, confidence = account_match
                # Solo usar si la confianza es alta
                if confidence > 0.7:
                    result['account_id'] = account_id
                    result['account_name'] = account_name
                    result['account_confidence'] = confidence
                    
                    logger.info(f"Cuenta detectada directamente: {account_name} "
                               f"(confianza: {confidence:.2f})")
        
        return result
    

    
    def learn_from_transaction(self, payee: str, category_id: str, category_name: str, 
                             confidence: float = 1.0, is_correction: bool = False):
        """Aprende de una transacción exitosa para mejorar futuras predicciones"""
        if self.adaptive_learner and payee and category_id:
            self.adaptive_learner.learn_association(
                payee=payee,
                category_id=category_id, 
                category_name=category_name,
                confidence=confidence,
                is_correction=is_correction
            )
            logger.info(f"Aprendizaje registrado: {payee} → {category_name}")
    
    def get_payee_prediction(self, payee: str) -> Optional[Dict]:
        """Obtiene predicción específica para un payee"""
        if not self.adaptive_learner:
            return None
            
        prediction = self.adaptive_learner.predict_category(payee)
        if prediction:
            category_id, category_name, confidence = prediction
            return {
                'category_id': category_id,
                'category_name': category_name,
                'confidence': confidence,
                'source': 'adaptive_learning'
            }
        return None
    
    def get_learning_stats(self) -> Dict:
        """Obtiene estadísticas del sistema de aprendizaje"""
        if not self.adaptive_learner:
            return {}
        return self.adaptive_learner.get_learning_statistics()
    
    def get_parser_stats(self) -> Dict:
        """Devuelve estadísticas del parser LLM"""
        return {
            'llm_available': self.llm_parser is not None,
            'llm_enabled': True,
            'parser_type': 'llm_only'
        }
    
    def get_expense_examples(self) -> List[str]:
        """Devuelve ejemplos de mensajes válidos para el usuario"""
        return [
            "Gasté $50000 en comida en Éxito",
            "$25000 transporte Uber con mi rappi card",
            "Almorcé en McDonald's, me gasté como 25 lucas",
            "Uber al aeropuerto 80k usando bancolombia",
            "Compras del super: 150 mil pesos en efectivo",
            "Netflix mensual 15.900 con mi nu card",
            "Gasolina 60000 con daviplata"
        ]
