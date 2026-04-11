import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
from openai import OpenAI
from dotenv import load_dotenv

from domain.time_utils import user_now, DEFAULT_TIMEZONE

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class LLMExpenseParser:
    """Expense parser powered by OpenAI GPT."""
    
    def __init__(self, ynab_categories: list = None, ynab_accounts: list = None):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no configurada en el archivo .env")
        
        self.client = OpenAI(api_key=self.api_key)
        self.ynab_categories = ynab_categories or []
        self.ynab_accounts = ynab_accounts or []
        
        # The prompt is generated dynamically from the current categories and accounts
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

{learning_hints_section}

{date_context}

RESPONDE SIEMPRE EN FORMATO JSON con esta estructura exacta:
{{
    "amount": <número_decimal>,
    "category": "<categoría_exacta_de_la_lista>",
    "payee": "<lugar_o_comercio>",
    "account": "<cuenta_exacta_de_la_lista_o_null>",
    "memo": "<mensaje_original>",
    "date": "<YYYY-MM-DD_o_null>",
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
        """Update the available YNAB category list."""
        self.ynab_categories = categories
        logger.info(f"Updated {len(categories)} YNAB categories for the LLM")
    
    def update_accounts(self, accounts: list):
        """Update the available YNAB account list."""
        self.ynab_accounts = accounts
        logger.info(f"Updated {len(accounts)} YNAB accounts for the LLM")
    
    def _get_date_context(self, timezone_str: str = DEFAULT_TIMEZONE) -> str:
        """Build the current date context injected into LLM prompts."""
        now = user_now(timezone_str)
        dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        dia_semana = dias_semana[now.weekday()]
        fecha_actual = now.strftime("%Y-%m-%d")
        return (
            f"FECHA ACTUAL DEL SISTEMA: {fecha_actual} ({dia_semana})\n\n"
            "DETECCIÓN DE FECHAS:\n"
            "- Si el mensaje menciona una fecha (relativa como \"ayer\", \"anteayer\", \"el lunes\", "
            "\"la semana pasada\" o absoluta como \"24/07\", \"el 5 de marzo\", \"el 3\"), "
            "resuélvela a formato YYYY-MM-DD.\n"
            "- Para fechas absolutas sin año (ej: \"24/07\"): usa la ocurrencia más reciente en el pasado "
            "respecto a la fecha actual. Si la fecha aún no ha pasado este año, usa el año anterior.\n"
            "- Para fechas futuras explícitas (ej: \"mañana\", \"el viernes\"): resuelve normalmente.\n"
            "- Si no hay mención de fecha, devuelve date: null."
        )

    def _generate_system_prompt(self, timezone_str: str = DEFAULT_TIMEZONE, learning_hints: Optional[str] = None) -> str:
        """Build the system prompt with the current categories and accounts."""
        # Category section
        if self.ynab_categories:
            categories_text = "CATEGORÍAS DISPONIBLES EN TU PRESUPUESTO YNAB:\n"
            for i, category in enumerate(self.ynab_categories[:100], 1):  # Expanded to 100
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
        
        # Account section
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

        if learning_hints and learning_hints.strip():
            learning_hints_text = (
                "HISTORIAL DE CATEGORIZACIÓN DEL USUARIO:\n"
                "Estos son los patrones de categorización previos del usuario. Úsalos como contexto adicional,\n"
                "pero PRIORIZA las pistas del mensaje actual (ej: si dice \"internet\", elige la categoría de internet\n"
                "aunque el historial muestre otra categoría como más frecuente).\n\n"
                f"{learning_hints}"
            )
        else:
            learning_hints_text = ""
        
        return self.base_system_prompt.format(
            categories_section=categories_text,
            accounts_section=accounts_text,
            learning_hints_section=learning_hints_text,
            date_context=self._get_date_context(timezone_str),
        )

    def _generate_receipt_system_prompt(self, timezone_str: str = DEFAULT_TIMEZONE, learning_hints: Optional[str] = None) -> str:
        """Build the system prompt used to analyze receipt images."""
        # Reuse category prompt logic
        if self.ynab_categories:
            categories_text = "CATEGORÍAS DISPONIBLES EN TU PRESUPUESTO YNAB:\n"
            for category in self.ynab_categories[:100]:
                categories_text += f"- {category['name']}\n"
            categories_text += "\n⚠️ REGLA DE ORO: Mapea el recibo a la categoría más semánticamente cercana de la lista anterior."
        else:
            categories_text = "No hay categorías configuradas. Usa categorías generales."

        # Reuse account prompt logic
        if self.ynab_accounts:
            accounts_text = "CUENTAS DISPONIBLES:\n"
            for account in self.ynab_accounts:
                accounts_text += f"- {account}\n"
        else:
            accounts_text = "No hay cuentas configuradas."

        if learning_hints and learning_hints.strip():
            learning_hints_section = (
                "\nHISTORIAL DE CATEGORIZACIÓN DEL USUARIO:\n"
                "Estos son los patrones de categorización previos del usuario. Úsalos como contexto adicional,\n"
                "pero PRIORIZA las pistas del recibo actual (ej: si el recibo es de una tienda de internet,\n"
                "elige la categoría de internet aunque el historial muestre otra categoría como más frecuente).\n\n"
                f"{learning_hints}"
            )
        else:
            learning_hints_section = ""

        return f"""Eres un experto en analizar recibos, facturas y tickets de venta en español colombiano.
Tu tarea es extraer la información de un gasto a partir de una IMAGEN de un recibo.

{categories_text}

{accounts_text}
{learning_hints_section}
INSTRUCCIONES ESPECÍFICAS PARA RECIBOS:
1. **Monto Total**: Extrae el valor total pagado (incluyendo impuestos y propinas si están en el total).
2. **Lugar/Payee**: Identifica el nombre del establecimiento (ej: "Éxito", "Restaurante El Corral", "Gasolinera Terpel").
3. **Categoría**: Elige la categoría más adecuada de la lista proporcionada basado en el lugar y los productos comprados.
4. **Memo**: Genera un resumen breve de lo comprado (ej: "Almuerzo: Hamburguesa y soda", "Mercado quincenal").
5. **Fecha**: Si la fecha es visible, inclúyela al inicio del memo en formato [DD/MM] y también en el campo "date" en formato YYYY-MM-DD.
6. **Cuenta**: Si el recibo indica medio de pago (ej: "VISA ****1234") y coincide con una de las CUENTAS DISPONIBLES, selecciónala. De lo contrario, usa null.

CONTEXTO COLOMBIANO:
- Moneda: Pesos Colombianos (COP). Los montos suelen ser números grandes (ej: 45000, 120000).
- Impuestos: IVA (19%) e Impoconsumo (8%) suelen estar incluidos en el total.

{self._get_date_context(timezone_str)}

RESPONDE SIEMPRE EN FORMATO JSON con esta estructura exacta:
{{
    "amount": <número_decimal>,
    "category": "<categoría_exacta_de_la_lista>",
    "payee": "<lugar_o_comercio>",
    "account": "<cuenta_exacta_de_la_lista_o_null>",
    "memo": "<resumen_breve_del_recibo>",
    "date": "<YYYY-MM-DD_o_null>",
    "confidence": <0.0_a_1.0>
}}

⚠️ REGLAS CRÍTICAS:
- Si la imagen NO es un recibo, factura o ticket de venta, o es totalmente ilegible, devuelve confidence: 0.0.
- Si faltan datos críticos (monto o lugar), devuelve confidence: 0.0.
- No inventes datos. Si algo no es claro, usa lo más probable o baja el confidence.
"""

    def _generate_message_system_prompt(self, timezone_str: str = DEFAULT_TIMEZONE, learning_hints: Optional[str] = None) -> str:
        """Build the system prompt for intent classification and message parsing."""
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

        if learning_hints and learning_hints.strip():
            learning_hints_section = (
                "HISTORIAL DE CATEGORIZACIÓN DEL USUARIO:\n"
                "Estos son los patrones de categorización previos del usuario. Úsalos como contexto adicional,\n"
                "pero PRIORIZA las pistas del mensaje actual (ej: si dice \"internet\", elige la categoría de internet\n"
                "aunque el historial muestre otra categoría como más frecuente).\n\n"
                f"{learning_hints}"
            )
        else:
            learning_hints_section = ""

        return f"""Eres un asistente que clasifica mensajes de usuarios de una app de presupuesto en español colombiano.

Debes determinar si el mensaje es un GASTO o una CONSULTA sobre el presupuesto.

CONSULTAS: mensajes que preguntan sobre saldos, presupuesto, o estado financiero.
Palabras clave de consulta: "cuánto", "cómo va", "resumen", "saldo", "debo", "queda", "he gastado", "presupuesto", "disponible", "balance".

GASTOS: mensajes que reportan un gasto realizado. Contienen un monto y un lugar/concepto.

{categories_text}

{accounts_text}

{learning_hints_section}

{self._get_date_context(timezone_str)}

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
    "date": "<YYYY-MM-DD_o_null>",
    "confidence": <0.0_a_1.0>
}}

Para GASTOS COMPARTIDOS ("a medias", "mitad", "compartido", "split", "con [persona]", "[persona] pagó", "[persona] gastó", "por mí", "me compró", "para mí", "por [persona]", "para [persona]", "le presté", "le compré"):
{{
    "intent": "shared_expense",
    "amount": <número_decimal>,
    "category": "<categoría_exacta_de_la_lista>",
    "payee": "<lugar>",
    "account": "<cuenta_exacta_de_la_lista_o_null>",
    "memo": "<mensaje_original>",
    "date": "<YYYY-MM-DD_o_null>",
    "confidence": <0.0_a_1.0>,
    "person": "<nombre_de_la_persona>",
    "proportion": "<fraccion_o_null>",
    "split_amount": <número_o_null>,
    "payer": "user" | "other"
}}

REGLAS CRÍTICAS:
1. "category_balance": pregunta por UNA categoría específica. DEBES mapear lo que diga el usuario al nombre exacto de la lista de CATEGORÍAS DISPONIBLES.
2. "account_balance": pregunta por UNA cuenta específica. DEBES mapear al nombre exacto de la lista de CUENTAS DISPONIBLES.
3. "budget_summary": pregunta general sobre el presupuesto (ej: "cómo va mi presupuesto"). query_target debe ser null.
4. Para GASTOS, la categoría DEBE ser una de la lista de CATEGORÍAS DISPONIBLES.
5. NO inventes nombres. Si no encuentras un match claro, usa el nombre más probable o devuelve confidence baja.
6. "payer" en gastos compartidos: debe ser "other" si otra persona pagó el gasto (ej. "Eli gastó 50k en carulla conmigo", "Juan pagó la cena"), o "user" si el usuario lo pagó (ej. "pagué el almuerzo con Juan a medias"). Si no está claro quién pagó, usa "user".
7. "proportion" y "split_amount" en gastos compartidos — son mutuamente excluyentes, usa UNO o ninguno:

   a) "proportion": SIEMPRE es la fracción del USUARIO (nunca la de la otra persona). CRÍTICO: si alguien dice "X son por [persona]" o "la parte de [persona] es X", eso es la parte de LA OTRA PERSONA, NO del usuario.
      - "a medias" → proportion: "1/2", split_amount: null
      - "mi parte es 1/3" → proportion: "1/3", split_amount: null
      - "2/3 son míos" → proportion: "2/3", split_amount: null
      - "por mí" / "me compró" / "para mí" + payer:other → proportion: "1", split_amount: null
      - "por [persona]" / "para [persona]" / "le presté" / "le compré" + payer:user → proportion: "0", split_amount: null (100% es para la otra persona, el usuario no tiene parte)
      - Sin lenguaje de proporción → proportion: null (default 50/50)

   b) "split_amount": cuando el usuario especifica un MONTO FIJO para la OTRA PERSONA (ej: "36700 son por Juan", "la parte de Eli es 25000"). Devuelve ese monto en split_amount y pon proportion: null.
      - "gasté 60000, 36700 son por Juan" → proportion: null, split_amount: 36700
      - "almuerzo 80000, la parte de Eli es 25000" → proportion: null, split_amount: 25000

   c) Si no se especifica ni proporción ni monto fijo: proportion: null, split_amount: null → se asume 50/50.

EJEMPLOS DE GASTOS COMPARTIDOS:
- "gasté 60000 en restaurante con Juan, 2/3 son míos" → proportion: "2/3", split_amount: null, payer: "user" (la parte del usuario es 2/3)
- "gasté 60000 en restaurante, 36700 son por Juan" → proportion: null, split_amount: 36700, payer: "user" (Juan debe 36700 fijo)
- "almuerzo 50000 a medias con Eli" → proportion: "1/2", split_amount: null, payer: "user"
- "Eli pagó 100k por mí" → proportion: "1", split_amount: null, payer: "other" (usuario debe el 100%)
- "Gasté 100k en Carulla por Eli" → proportion: "0", split_amount: null, payer: "user" (100% es para Eli, préstamo)
- "Le presté 50000 a Juan para farmacia" → proportion: "0", split_amount: null, payer: "user" (100% es para Juan)
- "Pagué 80k en supermercado para María" → proportion: "0", split_amount: null, payer: "user" (100% es para María)
"""

    def _strip_markdown_code_blocks(self, content: str) -> str:
        """Strip Markdown code fences when present."""
        content = content.strip()
        if content.startswith("```"):
            # Remove the opening fence line (```json or ```)
            lines = content.split("\n")
            if len(lines) > 2:
                # Drop any remaining fence lines
                content = "\n".join([line for line in lines if not line.strip().startswith("```")])
        return content.strip()

    def parse_message(self, message: str, timezone_str: str = DEFAULT_TIMEZONE, learning_hints: Optional[str] = None) -> Optional[Dict]:
        """
        Classify the message intent and return the corresponding structure.

        Returns:
            Dict with intent "expense", "shared_expense", or "query", or None on failure
        """
        try:
            system_prompt = self._generate_message_system_prompt(timezone_str, learning_hints=learning_hints)

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
                    logger.error(f"Response missing intent or confidence: {result}")
                    return None

                if not isinstance(result['confidence'], (int, float)) or not (0 <= result['confidence'] <= 1):
                    logger.error(f"Invalid confidence value: {result['confidence']}")
                    return None

                result['confidence'] = float(result['confidence'])

                if result['intent'] == 'query':
                    if 'query_type' not in result:
                        logger.error(f"Query response missing query_type: {result}")
                        return None
                    if result['query_type'] not in ('category_balance', 'account_balance', 'budget_summary'):
                        logger.error(f"Invalid query_type: {result['query_type']}")
                        return None
                elif result['intent'] == 'expense':
                    required = ['amount', 'category', 'payee', 'memo']
                    if not all(f in result for f in required):
                        logger.error(f"Expense response missing required fields: {result}")
                        return None
                    if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                        logger.error(f"Invalid amount: {result['amount']}")
                        return None
                    result['amount'] = float(result['amount'])
                elif result['intent'] == 'shared_expense':
                    required = ['amount', 'category', 'payee', 'memo', 'person']
                    if not all(f in result for f in required):
                        logger.error(f"Shared expense response missing required fields: {result}")
                        return None
                    if not result.get('person') or not str(result['person']).strip():
                        logger.error(f"Shared expense response missing person: {result}")
                        return None
                    if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                        logger.error(f"Invalid amount: {result['amount']}")
                        return None
                    result['amount'] = float(result['amount'])
                    # Validate and normalise payer field (defaults to 'user')
                    payer = result.get('payer', 'user')
                    if payer not in ('user', 'other'):
                        logger.warning(f"Invalid payer '{payer}', defaulting to 'user'")
                        payer = 'user'
                    result['payer'] = payer
                    # Validate and normalise split_amount field
                    split_amount = result.get('split_amount')
                    if split_amount is not None:
                        if isinstance(split_amount, (int, float)) and split_amount > 0:
                            result['split_amount'] = float(split_amount)
                        else:
                            logger.warning(f"Invalid split_amount '{split_amount}', ignoring it")
                            result['split_amount'] = None
                    else:
                        result['split_amount'] = None
                else:
                    logger.error(f"Unknown intent: {result['intent']}")
                    return None

                return result

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing OpenAI JSON response: {content}, Error: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calling the OpenAI API: {e}")
            return None

    def parse_expense(self, message: str, timezone_str: str = DEFAULT_TIMEZONE, learning_hints: Optional[str] = None) -> Optional[Dict]:
        """
        Parse an expense message with OpenAI GPT.

        Args:
            message: User message describing an expense
            timezone_str: IANA timezone string for date context

        Returns:
            Dict with expense information, or None on failure
        """
        try:
            # Build a dynamic prompt with the current categories
            system_prompt = self._generate_system_prompt(timezone_str, learning_hints=learning_hints)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,  # Lower temperature for more consistent responses
                max_tokens=200
            )
            
            # Extract the response content
            content = response.choices[0].message.content.strip()
            content = self._strip_markdown_code_blocks(content)
            
            # Parse the JSON payload
            try:
                result = json.loads(content)
                
                # Validate required fields
                required_fields = ['amount', 'category', 'payee', 'memo', 'confidence']
                if not all(field in result for field in required_fields):
                    logger.error(f"OpenAI response missing required fields: {result}")
                    return None
                
                # Validate types
                if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                    logger.error(f"Invalid amount: {result['amount']}")
                    return None
                
                if not isinstance(result['confidence'], (int, float)) or not (0 <= result['confidence'] <= 1):
                    logger.error(f"Invalid confidence value: {result['confidence']}")
                    return None
                
                # Normalize numeric types for consistency
                result['amount'] = float(result['amount'])
                result['confidence'] = float(result['confidence'])
                
                logger.debug(f"LLM parsed message successfully: {message} -> {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing OpenAI JSON response: {content}, Error: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling the OpenAI API: {e}")
            return None

    def parse_receipt_image(self, image_base64: str, caption: str = None, timezone_str: str = DEFAULT_TIMEZONE, learning_hints: Optional[str] = None) -> Optional[Dict]:
        """
        Analyze a base64-encoded receipt image with OpenAI GPT-4o-mini Vision.

        Args:
            image_base64: Base64-encoded receipt image.
            caption: Optional text provided alongside the image.

        Returns:
            Dict with expense information, or None on failure.
        """
        try:
            system_prompt = self._generate_receipt_system_prompt(timezone_str, learning_hints=learning_hints)

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
                    logger.error(f"Vision response missing required fields: {result}")
                    return None

                if not isinstance(result['amount'], (int, float)) or result['amount'] <= 0:
                    logger.error(f"Invalid amount from Vision: {result['amount']}")
                    return None

                if not isinstance(result['confidence'], (int, float)) or not (0 <= result['confidence'] <= 1):
                    logger.error(f"Invalid confidence value from Vision: {result['confidence']}")
                    return None

                result['amount'] = float(result['amount'])
                result['confidence'] = float(result['confidence'])

                return result

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Vision JSON response: {content}, Error: {e}")
                return None

        except Exception as e:
            logger.error(f"Error calling the OpenAI Vision API: {e}")
            return None
    
    def test_parsing(self):
        """Run a simple parser smoke test with sample messages."""
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
        
        print("Running LLM expense parser smoke test:\n")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"Test {i}: '{test_case}'")
            result = self.parse_expense(test_case)
            
            if result and result['confidence'] > 0.5:
                print(f"  ✅ Parseado exitosamente (confianza: {result['confidence']:.2f}):")
                print(f"     💰 Cantidad: ${result['amount']:,.0f}")
                print(f"     🏷️ Categoría: {result['category']}")
                print(f"     🏪 Lugar: {result['payee']}")
            else:
                print("  Could not parse the message or confidence was too low")
            
            print()


if __name__ == "__main__":
    try:
        parser = LLMExpenseParser()
        parser.test_parsing()
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure OPENAI_API_KEY is configured in your .env file")
