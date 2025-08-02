import os
import logging
from typing import Dict, List, Optional, Tuple
from integrations.ynab_client import YNABClient

logger = logging.getLogger(__name__)


class YNABAccountManager:
    """
    Gestor de cuentas YNAB para mapeo inteligente de nombres de cuentas
    
    Carga las cuentas reales del presupuesto YNAB y proporciona funcionalidades
    para buscar y mapear nombres de cuentas mencionados en mensajes de gastos.
    """
    
    def __init__(self, ynab_client: YNABClient):
        self.ynab_client = ynab_client
        self.accounts = {}  # account_id -> account_data
        self.account_keywords = {}  # account_id -> [keywords]
        self.budget_id = None
    
    def load_accounts(self, budget_id: str) -> bool:
        """
        Carga las cuentas del presupuesto YNAB
        
        Args:
            budget_id: ID del presupuesto YNAB
            
        Returns:
            True si se cargaron exitosamente, False en caso contrario
        """
        try:
            accounts = self.ynab_client.get_accounts(budget_id)
            if not accounts:
                logger.error("No se pudieron cargar las cuentas de YNAB")
                return False
            
            self.budget_id = budget_id
            self.accounts = {}
            self.account_keywords = {}
            
            # Procesar solo cuentas activas (no cerradas)
            active_accounts = [acc for acc in accounts if not acc.get('closed', False)]
            
            for account in active_accounts:
                account_id = account['id']
                account_name = account['name']
                
                self.accounts[account_id] = {
                    'id': account_id,
                    'name': account_name,
                    'type': account.get('type', 'checking'),
                    'balance': account.get('balance', 0),
                    'closed': account.get('closed', False)
                }
                
                # Generar palabras clave para esta cuenta
                keywords = self._generate_account_keywords(account_name)
                self.account_keywords[account_id] = keywords
            
            logger.info(f"Cargadas {len(self.accounts)} cuentas activas de YNAB")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando cuentas YNAB: {e}")
            return False
    
    def _generate_account_keywords(self, account_name: str) -> List[str]:
        """
        Genera palabras clave para una cuenta basándose en su nombre
        
        Args:
            account_name: Nombre de la cuenta
            
        Returns:
            Lista de palabras clave
        """
        keywords = []
        
        # Nombre completo (normalizado)
        normalized_name = account_name.lower().strip()
        keywords.append(normalized_name)
        
        # Palabras individuales
        words = normalized_name.split()
        keywords.extend(words)
        
        # Variaciones comunes de nombres de cuentas colombianas
        account_variations = {
            'bancolombia': ['bancolombia', 'banco colombia', 'bco colombia'],
            'davivienda': ['davivienda', 'banco davivienda', 'davi'],
            'bbva': ['bbva', 'banco bbva'],
            'banco de bogota': ['banco de bogota', 'bogota', 'bdb'],
            'banco popular': ['banco popular', 'popular'],
            'colpatria': ['colpatria', 'banco colpatria'],
            'av villas': ['av villas', 'banco av villas', 'villas'],
            'banco caja social': ['caja social', 'bcsc'],
            'nequi': ['nequi'],
            'daviplata': ['daviplata', 'davi plata'],
            'rappi card': ['rappi card', 'rappi', 'tarjeta rappi'],
            'nu': ['nu', 'nubank', 'tarjeta nu'],
            'lulo bank': ['lulo', 'lulo bank'],
            'banco agrario': ['agrario', 'banco agrario'],
            'banco occidente': ['occidente', 'banco occidente'],
            'itau': ['itau', 'banco itau'],
            'scotiabank': ['scotiabank', 'scotia'],
            'citibank': ['citibank', 'citi'],
            'mastercard': ['mastercard', 'master card', 'master'],
            'visa': ['visa', 'tarjeta visa'],
            'american express': ['american express', 'amex', 'american'],
            'efectivo': ['efectivo', 'cash', 'dinero en efectivo']
        }
        
        # Buscar variaciones específicas
        for canonical, variations in account_variations.items():
            if any(var in normalized_name for var in variations):
                keywords.extend(variations)
                break
        
        # Remover duplicados y devolver
        return list(set(keywords))
    
    def find_best_account(self, text: str) -> Optional[Tuple[str, str, float]]:
        """
        Encuentra la mejor cuenta que coincida con el texto dado
        
        Args:
            text: Texto donde buscar menciones de cuentas
            
        Returns:
            Tupla (account_id, account_name, confidence) o None si no encuentra
        """
        if not self.accounts:
            return None
        
        text_lower = text.lower()
        best_match = None
        best_score = 0.0
        
        for account_id, keywords in self.account_keywords.items():
            account_data = self.accounts[account_id]
            score = 0.0
            
            # Buscar coincidencias de palabras clave
            for keyword in keywords:
                if keyword in text_lower:
                    # Puntuación basada en longitud de la palabra clave
                    keyword_score = len(keyword) / len(text_lower)
                    
                    # Bonus por coincidencia exacta
                    if keyword == account_data['name'].lower():
                        keyword_score *= 2.0
                    
                    score += keyword_score
            
            # Normalizar puntuación
            if score > 0:
                normalized_score = min(1.0, score)
                
                if normalized_score > best_score:
                    best_score = normalized_score
                    best_match = (account_id, account_data['name'], normalized_score)
        
        # Solo devolver si la confianza es suficientemente alta
        if best_match and best_score >= 0.3:
            return best_match
        
        return None
    
    def get_accounts_list(self) -> List[Dict]:
        """
        Obtiene la lista de todas las cuentas cargadas
        
        Returns:
            Lista de diccionarios con información de cuentas
        """
        return list(self.accounts.values())
    
    def get_account_by_id(self, account_id: str) -> Optional[Dict]:
        """
        Obtiene información de una cuenta por su ID
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            Diccionario con información de la cuenta o None
        """
        return self.accounts.get(account_id)
    
    def get_account_names_for_llm(self) -> List[str]:
        """
        Obtiene lista de nombres de cuentas para usar en prompts LLM
        
        Returns:
            Lista de nombres de cuentas
        """
        return [account['name'] for account in self.accounts.values()]


if __name__ == "__main__":
    # Script de prueba
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
    budget_id = os.getenv('YNAB_BUDGET_ID')
    
    if not ynab_token or not budget_id:
        print("❌ Faltan tokens de configuración")
        exit(1)
    
    print("🧪 Probando gestor de cuentas YNAB:\n")
    
    # Inicializar cliente y gestor
    ynab_client = YNABClient(ynab_token)
    account_manager = YNABAccountManager(ynab_client)
    
    # Cargar cuentas
    success = account_manager.load_accounts(budget_id)
    if not success:
        print("❌ Error cargando cuentas")
        exit(1)
    
    # Mostrar cuentas cargadas
    accounts = account_manager.get_accounts_list()
    print(f"📊 Cuentas cargadas ({len(accounts)}):")
    for account in accounts:
        print(f"  • {account['name']} ({account['type']})")
    
    # Probar búsquedas
    test_phrases = [
        "con mi rappi card",
        "usando bancolombia",
        "tarjeta nu",
        "efectivo",
        "con mi visa",
        "nequi",
        "daviplata"
    ]
    
    print(f"\n🔍 Pruebas de búsqueda:")
    for phrase in test_phrases:
        result = account_manager.find_best_account(phrase)
        if result:
            account_id, account_name, confidence = result
            print(f"  '{phrase}' → {account_name} (confianza: {confidence:.2f})")
        else:
            print(f"  '{phrase}' → Sin coincidencia")
    
    # Lista para LLM
    print(f"\n🤖 Nombres para LLM:")
    llm_names = account_manager.get_account_names_for_llm()
    for name in llm_names:
        print(f"  • {name}")
