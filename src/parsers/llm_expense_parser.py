import os
import json
import logging
from typing import Dict, Optional, List
from openai import OpenAI
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)


class LLMExpenseParser:
    """Parser inteligente de gastos usando OpenAI GPT"""
    
    def __init__(self, ynab_categories: list = None, ynab_accounts: list = None):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no configurada en el archivo .env")
        
        self.client = OpenAI(api_key=self.api_key)
        self.ynab_categories = ynab_categories or []
        self.ynab_accounts = ynab_accounts or []
        
        # El prompt se genera dinámicamente con las categorías y cuentas reales
        self.base_system_prompt = """
Eres un asistente especializado en parsear mensajes de gastos en español colombiano para una aplicación de presupuesto.

Tu tarea es extraer información de mensajes informales sobre gastos y convertirla en un formato estructurado.

FORMATO DE MONEDA:
- Los usuarios usan pesos colombianos
- Formatos comunes: "$40000", "40000", "40 mil", "40k", "40 lucas"
- Decimales con coma: "40000,50" o "40.000,50"
- "Lucas" = miles (ej: "25 lucas" = 25000)

{categories_section}

{accounts_section}

RESPONDE SIEMPRE EN FORMATO JSON con esta estructura exacta:
{{
    "amount": <número_decimal>,
    "category": "<categoría_exacta_de_la_lista>",
    "payee": "<lugar_o_comercio>",
    "account": "<cuenta_exacta_de_la_lista_o_null>",
    "memo": "<mensaje_original>",
    "confidence": <0.0_a_1.0>
}}

EJEMPLOS:
- "Me pedi en McDonald's, me gasté como 25 lucas" → amount: 25000.0, category: "🥗 Meal delivery", payee: "McDonald's", account: null
- "Uber al aeropuerto 80k con mi rappi card" → amount: 80000.0, category: "🚙 Rideshare (Uber/Lyft/etc.)", payee: "Uber", account: "Rappi Card"
- "Compras del super: 150 mil pesos en efectivo" → amount: 150000.0, category: "🛒 Groceries", payee: "Supermercado", account: "Efectivo"
- "Netflix mensual 15.900 con bancolombia" → amount: 15900.0, category: "📺Netflix", payee: "Netflix", account: "Bancolombia"
- "Me gasté $3000 en Carulla con mi Nu Card" → amount: 3000.0, category: "🛒 Groceries", payee: "Carulla", account: "Nu Card"
- "Compre una botella en MercadoLibre por 12345 con mi nu card → amount: 12345.0, category: "🛍️Shopping (MercadoLibre/Amazon/etc.)", payee: "MercadoLibre", account: "Nu Card" 

⚠️ REGLAS CRÍTICAS:
1. **CATEGORÍA vs CUENTA**: 
   - CATEGORÍA = ¿PARA QUÉ es el gasto? (comida, transporte, entretenimiento)
   - CUENTA = ¿CÓMO se pagó? (tarjeta, efectivo, banco)
   - NUNCA uses nombres de cuentas como categorías
   - NUNCA uses nombres de categorías como cuentas

2. **VALIDACIÓN**:
   - La categoría DEBE ser de la lista de categorías YNAB
   - La cuenta DEBE ser de la lista de cuentas YNAB o null
   - Si "Carulla" → categoría: "Groceries", NO "Nu Card"
   - Si "con mi Nu Card" → account: "Nu Card", NO categoría

3. **PROCESAMIENTO**:
   - Identifica el LUGAR/COMERCIO para determinar categoría
   - Identifica "con mi", "usando", "en" para determinar cuenta
   - Usa EXACTAMENTE los nombres de las listas proporcionadas
   - Si no detectas cuenta específica, usa account: null
   - Si no puedes parsear el mensaje, devuelve confidence: 0.0
"""
    
    def update_categories(self, categories: list):
        """Actualiza la lista de categorías YNAB disponibles"""
        self.ynab_categories = categories
        logger.info(f"Actualizadas {len(categories)} categorías YNAB para LLM")
    
    def update_accounts(self, accounts: list):
        """Actualiza la lista de cuentas YNAB disponibles"""
        self.ynab_accounts = accounts
        logger.info(f"Actualizadas {len(accounts)} cuentas YNAB para LLM")
    
    def _generate_system_prompt(self) -> str:
        """Genera el prompt del sistema con las categorías y cuentas actuales"""
        # Sección de categorías
        if self.ynab_categories:
            categories_text = "CATEGORÍAS DISPONIBLES EN TU PRESUPUESTO YNAB:\n"
            for i, category in enumerate(self.ynab_categories[:20], 1):  # Limitar a 20 para no sobrecargar
                categories_text += f"- {category['name']}\n"
            
            if len(self.ynab_categories) > 20:
                categories_text += f"... y {len(self.ynab_categories) - 20} categorías más\n"
            
            categories_text += "\nUsa EXACTAMENTE estos nombres de categorías."
        else:
            categories_text = """CATEGORÍAS COMUNES:
- Comida/Alimentación: supermercado, groceries, mercado, comida
- Transporte: uber, taxi, bus, metro, gasolina, combustible
- Entretenimiento: cine, netflix, spotify, juegos, diversión
- Salud: medicina, doctor, farmacia, hospital, droguería
- Ropa: vestimenta, zapatos, clothing, ropa"""
        
        # Sección de cuentas
        if self.ynab_accounts:
            accounts_text = "CUENTAS DISPONIBLES EN TU PRESUPUESTO YNAB:\n"
            for account in self.ynab_accounts:
                accounts_text += f"- {account}\n"
            
            accounts_text += "\nDETECCIÓN DE CUENTAS:\n"
            accounts_text += "- Busca menciones como: 'con mi [cuenta]', 'usando [cuenta]', 'en [cuenta]'\n"
            accounts_text += "- Ejemplos: 'con mi rappi card', 'usando bancolombia', 'en efectivo'\n"
            accounts_text += "- Si detectas una cuenta, usa EXACTAMENTE el nombre de la lista\n"
            accounts_text += "- Si no detectas cuenta específica, usa account: null"
        else:
            accounts_text = """DETECCIÓN DE CUENTAS:
- Busca menciones de cuentas/tarjetas en el mensaje
- Ejemplos: 'con mi rappi card', 'usando bancolombia', 'en efectivo'
- Si no detectas cuenta específica, usa account: null"""
        
        return self.base_system_prompt.format(
            categories_section=categories_text,
            accounts_section=accounts_text
        )
    
    def parse_expense(self, message: str) -> Optional[Dict]:
        """
        Parsea un mensaje usando OpenAI GPT
        
        Args:
            message: Mensaje del usuario sobre un gasto
            
        Returns:
            Dict con información del gasto o None si falla
        """
        try:
            # Generar prompt dinámico con categorías actuales
            system_prompt = self._generate_system_prompt()
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,  # Baja temperatura para respuestas más consistentes
                max_tokens=200
            )
            
            # Extraer el contenido de la respuesta
            content = response.choices[0].message.content.strip()
            
            # Parsear el JSON
            try:
                result = json.loads(content)
                
                # Validar que tenga los campos requeridos
                required_fields = ['amount', 'category', 'payee', 'memo', 'confidence']
                if not all(field in result for field in required_fields):
                    logger.error(f"Respuesta de OpenAI falta campos requeridos: {result}")
                    return None
                
                # Validar tipos
                if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                    logger.error(f"Cantidad inválida: {result['amount']}")
                    return None
                
                if not isinstance(result['confidence'], (int, float)) or not (0 <= result['confidence'] <= 1):
                    logger.error(f"Confianza inválida: {result['confidence']}")
                    return None
                
                # Convertir a float para consistencia
                result['amount'] = float(result['amount'])
                result['confidence'] = float(result['confidence'])
                
                logger.info(f"Parseo exitoso con LLM: {message} → {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON de OpenAI: {content}, Error: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error llamando a OpenAI API: {e}")
            return None
    
    def test_parsing(self):
        """Método para probar el parser con casos de ejemplo"""
        test_cases = [
            "Almorcé en McDonald's, me gasté como 25 lucas",
            "Uber al aeropuerto 80k",
            "Compras del super: 150 mil pesos",
            "Netflix mensual 15.900",
            "Gaste 50000 en Home Burguer",
            "Pagué la cuenta del restaurante, fueron como 45 mil",
            "Gasolina 60 lucas en la Esso",
            "Compré ropa en Zara por 120k"
        ]
        
        print("🧪 Probando LLM Expense Parser:\n")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"Test {i}: '{test_case}'")
            result = self.parse_expense(test_case)
            
            if result and result['confidence'] > 0.5:
                print(f"  ✅ Parseado exitosamente (confianza: {result['confidence']:.2f}):")
                print(f"     💰 Cantidad: ${result['amount']:,.0f}")
                print(f"     🏷️ Categoría: {result['category']}")
                print(f"     🏪 Lugar: {result['payee']}")
            else:
                print(f"  ❌ No se pudo parsear o baja confianza")
            
            print()


if __name__ == "__main__":
    try:
        parser = LLMExpenseParser()
        parser.test_parsing()
    except Exception as e:
        print(f"Error: {e}")
        print("Asegúrate de configurar OPENAI_API_KEY en tu archivo .env")
