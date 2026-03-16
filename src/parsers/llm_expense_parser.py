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

EJEMPLOS CORRECTOS:
- "Me pedi en McDonald's, me gasté como 25 lucas" → amount: 25000.0, category: "🥗 Meal delivery", payee: "McDonald's", account: null
- "Uber al aeropuerto 80k con mi rappi card" → amount: 80000.0, category: "🚙 Rideshare (Uber/Lyft/etc.)", payee: "Uber", account: "Rappi Card"
- "Compras del super: 150 mil pesos en efectivo" → amount: 150000.0, category: "🛒 Groceries", payee: "Supermercado", account: "Efectivo"
- "Netflix mensual 15.900 con bancolombia" → amount: 15900.0, category: "📺Netflix", payee: "Netflix", account: "Bancolombia"
- "Me gasté $3000 en Carulla con mi Nu Card" → amount: 3000.0, category: "🛒 Groceries", payee: "Carulla", account: "Nu Card"
- "Compre una botella en MercadoLibre por 12345 con mi nu card → amount: 12345.0, category: "🛍️Shopping (MercadoLibre/Amazon/etc.)", payee: "MercadoLibre", account: "Nu Card" 
- "Gasté 20k en productos de belleza en Éxito con mi Visa" → amount: 20000.0, category: "🧴 Personal Care", payee: "Éxito", account: "Visa"

EJEMPLOS INCORRECTOS (NO HACER ESTO):
- ❌ "Gasté 20k en productos de belleza en Éxito con mi Visa" → category: "Visa", account: null (MAL: usando cuenta como categoría)
- ❌ "Compré ropa en Zara con mi tarjeta" → category: "tarjeta", account: null (MAL: usando cuenta como categoría)

⚠️ REGLAS CRÍTICAS - ¡ATENCIÓN ESPECIAL A ESTAS REGLAS!:
1. **CATEGORÍA vs CUENTA - DISTINCIÓN CLAVE**: 
   - CATEGORÍA = ¿PARA QUÉ es el gasto? (comida, transporte, entretenimiento, cuidado personal, etc.)
   - CUENTA = ¿CÓMO se pagó? (tarjeta, efectivo, banco - solo nombres de cuentas reales)
   - NUNCA uses nombres de cuentas como categorías
   - NUNCA uses nombres de categorías como cuentas
   - NUNCA uses palabras genéricas como "tarjeta", "efectivo", "dinero" como categoría

2. **VALIDACIÓN IMPORTANTE**:
   - La categoría DEBE ser de la lista de categorías YNAB
   - La cuenta DEBE ser de la lista de cuentas YNAB o null
   - Si "Carulla" → categoría: "🛒 Groceries", NO "Nu Card", NO "tarjeta"
   - Si "con mi Nu Card" → account: "Nu Card", NO categoría
   - Si "productos de belleza" → categoría: "🧴 Personal Care", NO "tarjeta", NO "efectivo"

3. **PROCESAMIENTO DETALLADO**:
   - Identifica primero el LUGAR/COMERCIO y el TIPO DE PRODUCTO/SERVICIO para determinar categoría
   - Identifica "con mi", "usando", "en" + NOMBRE ESPECÍFICO para determinar cuenta
   - Usa EXACTAMENTE los nombres de las listas proporcionadas
   - Si no detectas cuenta específica, usa account: null
   - Si no puedes parsear el mensaje con alta confianza, devuelve confidence: 0.0
   - Si detectas que una cuenta se está usando como categoría, corrige automáticamente
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
            for i, category in enumerate(self.ynab_categories[:100], 1):  # Aumentado a 100
                categories_text += f"- {category['name']}\n"
            
            if len(self.ynab_categories) > 100:
                categories_text += f"... y {len(self.ynab_categories) - 100} categorías más\n"
            
            categories_text += "\n⚠️ REGLA DE ORO: Mapea el mensaje a la categoría más semánticamente cercana de la lista anterior. Usa EXACTAMENTE el nombre de la categoría, incluyendo emojis si los tiene."
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

    def _generate_receipt_system_prompt(self) -> str:
        """Genera el prompt del sistema específico para analizar imágenes de recibos"""
        # Reutilizar lógica de categorías
        if self.ynab_categories:
            categories_text = "CATEGORÍAS DISPONIBLES EN TU PRESUPUESTO YNAB:\n"
            for category in self.ynab_categories[:100]:
                categories_text += f"- {category['name']}\n"
            categories_text += "\n⚠️ REGLA DE ORO: Mapea el recibo a la categoría más semánticamente cercana de la lista anterior."
        else:
            categories_text = "No hay categorías configuradas. Usa categorías generales."

        # Reutilizar lógica de cuentas
        if self.ynab_accounts:
            accounts_text = "CUENTAS DISPONIBLES:\n"
            for account in self.ynab_accounts:
                accounts_text += f"- {account}\n"
        else:
            accounts_text = "No hay cuentas configuradas."

        return f"""Eres un experto en analizar recibos, facturas y tickets de venta en español colombiano.
Tu tarea es extraer la información de un gasto a partir de una IMAGEN de un recibo.

{categories_text}

{accounts_text}

INSTRUCCIONES ESPECÍFICAS PARA RECIBOS:
1. **Monto Total**: Extrae el valor total pagado (incluyendo impuestos y propinas si están en el total).
2. **Lugar/Payee**: Identifica el nombre del establecimiento (ej: "Éxito", "Restaurante El Corral", "Gasolinera Terpel").
3. **Categoría**: Elige la categoría más adecuada de la lista proporcionada basado en el lugar y los productos comprados.
4. **Memo**: Genera un resumen breve de lo comprado (ej: "Almuerzo: Hamburguesa y soda", "Mercado quincenal").
5. **Fecha**: Si la fecha es visible, inclúyela al inicio del memo en formato [DD/MM].
6. **Cuenta**: Si el recibo indica medio de pago (ej: "VISA ****1234") y coincide con una de las CUENTAS DISPONIBLES, selecciónala. De lo contrario, usa null.

CONTEXTO COLOMBIANO:
- Moneda: Pesos Colombianos (COP). Los montos suelen ser números grandes (ej: 45000, 120000).
- Impuestos: IVA (19%) e Impoconsumo (8%) suelen estar incluidos en el total.

RESPONDE SIEMPRE EN FORMATO JSON con esta estructura exacta:
{{
    "amount": <número_decimal>,
    "category": "<categoría_exacta_de_la_lista>",
    "payee": "<lugar_o_comercio>",
    "account": "<cuenta_exacta_de_la_lista_o_null>",
    "memo": "<resumen_breve_del_recibo>",
    "confidence": <0.0_a_1.0>
}}

⚠️ REGLAS CRÍTICAS:
- Si la imagen NO es un recibo, factura o ticket de venta, o es totalmente ilegible, devuelve confidence: 0.0.
- Si faltan datos críticos (monto o lugar), devuelve confidence: 0.0.
- No inventes datos. Si algo no es claro, usa lo más probable o baja el confidence.
"""
    
    def _generate_message_system_prompt(self) -> str:
        """Genera el prompt del sistema para clasificar intent y parsear mensajes"""
        categories_text = "No hay categorías disponibles."
        if self.ynab_categories:
            categories_text = "CATEGORÍAS DISPONIBLES:\n"
            for category in self.ynab_categories[:100]:
                categories_text += f"- {category['name']}\n"
            
            categories_text += "\nSi el usuario pregunta por una categoría (ej: 'comida'), búscala semánticamente en esta lista (ej: '🛒 Groceries') y devuelve el NOMBRE EXACTO."

        accounts_text = "No hay cuentas disponibles."
        if self.ynab_accounts:
            accounts_text = "CUENTAS DISPONIBLES:\n"
            for account in self.ynab_accounts:
                accounts_text += f"- {account}\n"
            
            accounts_text += "\nSi el usuario pregunta por una cuenta, usa el NOMBRE EXACTO de esta lista."

        return f"""Eres un asistente que clasifica mensajes de usuarios de una app de presupuesto en español colombiano.

Debes determinar si el mensaje es un GASTO o una CONSULTA sobre el presupuesto.

CONSULTAS: mensajes que preguntan sobre saldos, presupuesto, o estado financiero.
Palabras clave de consulta: "cuánto", "cómo va", "resumen", "saldo", "debo", "queda", "he gastado", "presupuesto", "disponible", "balance".

GASTOS: mensajes que reportan un gasto realizado. Contienen un monto y un lugar/concepto.

{categories_text}

{accounts_text}

RESPONDE EN JSON con UNA de estas tres estructuras:

Para CONSULTAS:
{{
    "intent": "query",
    "query_type": "category_balance" | "account_balance" | "budget_summary",
    "query_target": "<nombre_exacto_de_categoría_o_cuenta_o_null>",
    "confidence": <0.0_a_1.0>
}}

Para GASTOS:
{{
    "intent": "expense",
    "amount": <número_decimal>,
    "category": "<categoría_exacta_de_la_lista>",
    "payee": "<lugar>",
    "account": "<cuenta_exacta_de_la_lista_o_null>",
    "memo": "<mensaje_original>",
    "confidence": <0.0_a_1.0>
}}

Para GASTOS COMPARTIDOS ("a medias", "mitad", "compartido", "split", "con [persona]"):
{{
    "intent": "shared_expense",
    "amount": <número_decimal>,
    "category": "<categoría_exacta_de_la_lista>",
    "payee": "<lugar>",
    "account": "<cuenta_exacta_de_la_lista_o_null>",
    "memo": "<mensaje_original>",
    "confidence": <0.0_a_1.0>,
    "person": "<nombre_de_la_persona>",
    "proportion": "<fraccion_o_null>"
}}

REGLAS CRÍTICAS:
1. "category_balance": pregunta por UNA categoría específica. DEBES mapear lo que diga el usuario al nombre exacto de la lista de CATEGORÍAS DISPONIBLES.
2. "account_balance": pregunta por UNA cuenta específica. DEBES mapear al nombre exacto de la lista de CUENTAS DISPONIBLES.
3. "budget_summary": pregunta general sobre el presupuesto (ej: "cómo va mi presupuesto"). query_target debe ser null.
4. Para GASTOS, la categoría DEBE ser una de la lista de CATEGORÍAS DISPONIBLES.
5. NO inventes nombres. Si no encuentras un match claro, usa el nombre más probable o devuelve confidence baja.
"""

    def _strip_markdown_code_blocks(self, content: str) -> str:
        """Elimina bloques de código Markdown si existen"""
        content = content.strip()
        if content.startswith("```"):
            # Eliminar la primera línea (```json o ```)
            lines = content.split("\n")
            if len(lines) > 2:
                # Filtrar las líneas que empiezan con ```
                content = "\n".join([line for line in lines if not line.strip().startswith("```")])
        return content.strip()

    def parse_message(self, message: str) -> Optional[Dict]:
        """
        Clasifica el intent del mensaje y retorna la estructura correspondiente.

        Returns:
            Dict con intent "expense" o "query", o None si falla
        """
        try:
            system_prompt = self._generate_message_system_prompt()

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,
                max_tokens=300
            )

            content = response.choices[0].message.content.strip()
            content = self._strip_markdown_code_blocks(content)

            try:
                result = json.loads(content)

                if 'intent' not in result or 'confidence' not in result:
                    logger.error(f"Respuesta sin intent o confidence: {result}")
                    return None

                if not isinstance(result['confidence'], (int, float)) or not (0 <= result['confidence'] <= 1):
                    logger.error(f"Confianza inválida: {result['confidence']}")
                    return None

                result['confidence'] = float(result['confidence'])

                if result['intent'] == 'query':
                    if 'query_type' not in result:
                        logger.error(f"Query sin query_type: {result}")
                        return None
                    if result['query_type'] not in ('category_balance', 'account_balance', 'budget_summary'):
                        logger.error(f"query_type inválido: {result['query_type']}")
                        return None
                elif result['intent'] == 'expense':
                    required = ['amount', 'category', 'payee', 'memo']
                    if not all(f in result for f in required):
                        logger.error(f"Expense sin campos requeridos: {result}")
                        return None
                    if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                        logger.error(f"Cantidad inválida: {result['amount']}")
                        return None
                    result['amount'] = float(result['amount'])
                elif result['intent'] == 'shared_expense':
                    required = ['amount', 'category', 'payee', 'memo', 'person']
                    if not all(f in result for f in required):
                        logger.error(f"Shared expense sin campos requeridos: {result}")
                        return None
                    if not result.get('person') or not str(result['person']).strip():
                        logger.error(f"Shared expense sin persona: {result}")
                        return None
                    if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                        logger.error(f"Cantidad inválida: {result['amount']}")
                        return None
                    result['amount'] = float(result['amount'])
                else:
                    logger.error(f"Intent desconocido: {result['intent']}")
                    return None

                return result

            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON de OpenAI: {content}, Error: {e}")
                return None

        except Exception as e:
            logger.error(f"Error llamando a OpenAI API: {e}")
            return None

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
            content = self._strip_markdown_code_blocks(content)
            
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
                
                logger.debug(f"Parseo exitoso con LLM: {message} → {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON de OpenAI: {content}, Error: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error llamando a OpenAI API: {e}")
            return None

    def parse_receipt_image(self, image_base64: str, caption: str = None) -> Optional[Dict]:
        """
        Analiza una imagen de un recibo en base64 usando OpenAI GPT-4o-mini Vision.

        Args:
            image_base64: Imagen del recibo codificada en base64.
            caption: Texto opcional que acompaña a la imagen.

        Returns:
            Dict con información del gasto o None si falla.
        """
        try:
            system_prompt = self._generate_receipt_system_prompt()

            user_content = [
                {
                    "type": "text",
                    "text": "Analiza este recibo/ticket y extrae la información del gasto."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]

            if caption:
                user_content.append({
                    "type": "text",
                    "text": f"Contexto adicional proporcionado por el usuario: {caption}"
                })

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()
            content = self._strip_markdown_code_blocks(content)

            try:
                result = json.loads(content)

                required_fields = ['amount', 'category', 'payee', 'memo', 'confidence']
                if not all(field in result for field in required_fields):
                    logger.error(f"Respuesta de Vision falta campos requeridos: {result}")
                    return None

                if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                    logger.error(f"Cantidad inválida de Vision: {result['amount']}")
                    return None

                if not isinstance(result['confidence'], (int, float)) or not (0 <= result['confidence'] <= 1):
                    logger.error(f"Confianza inválida de Vision: {result['confidence']}")
                    return None

                result['amount'] = float(result['amount'])
                result['confidence'] = float(result['confidence'])

                return result

            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON de Vision: {content}, Error: {e}")
                return None

        except Exception as e:
            logger.error(f"Error llamando a OpenAI Vision API: {e}")
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
