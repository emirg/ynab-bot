import re
from typing import Dict, Optional, Tuple, List
from datetime import datetime


class ExpenseParser:
    """Parser para extraer información de gastos de mensajes de texto"""
    
    def __init__(self):
        # Patrones para diferentes formatos de mensaje (pesos colombianos)
        self.patterns = [
            # Formato: "Gasté 50000 en comida en Home Burguer"
            r'gast[éeó]\s*\$?([\d.,]+)\s+en\s+(.+?)(?:\s+en\s+(.+))?$',
            
            # Formato: "$50000 comida Home Burguer"
            r'^\$?([\d.,]+)\s+([^$]+?)(?:\s+(.+))?$',
            
            # Formato: "50000 pesos comida"
            r'^([\d.,]+)\s*pesos?\s+(.+)$',
            
            # Formato: "Compré comida por 50000 en Home Burguer"
            r'compr[éeó]\s+(.+?)\s+por\s+\$?([\d.,]+)\s*(?:en\s+(.+))?$',
        ]
        
        # Mapeo de categorías comunes
        self.category_mapping = {
            'comida': ['comida', 'food', 'alimentación', 'groceries', 'supermercado'],
            'transporte': ['transporte', 'uber', 'taxi', 'bus', 'metro', 'gasolina', 'combustible'],
            'entretenimiento': ['entretenimiento', 'cine', 'netflix', 'spotify', 'juegos'],
            'salud': ['salud', 'medicina', 'doctor', 'farmacia', 'hospital'],
            'ropa': ['ropa', 'vestimenta', 'zapatos', 'clothing'],
            'servicios': ['servicios', 'luz', 'agua', 'internet', 'teléfono'],
            'restaurante': ['restaurante', 'restaurant', 'comida rápida', 'delivery'],
        }
    
    def parse_expense(self, message: str) -> Optional[Dict]:
        """
        Parsea un mensaje y extrae información del gasto
        
        Returns:
            Dict con keys: amount, category, payee, memo
        """
        message = message.strip().lower()
        
        for pattern in self.patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return self._extract_expense_data(match, pattern, message)
        
        return None
    
    def _extract_expense_data(self, match, pattern, original_message: str) -> Dict:
        """Extrae los datos del gasto basado en el patrón coincidente"""
        groups = match.groups()
        
        # Inicializar datos
        expense_data = {
            'amount': 0.0,
            'category': '',
            'payee': '',
            'memo': original_message
        }
        
        # Determinar el orden de los grupos según el patrón
        if 'gast' in pattern:
            # Patrón: "Gasté $50 en comida en Walmart"
            expense_data['amount'] = self._parse_amount(groups[0])
            expense_data['category'] = self._normalize_category(groups[1])
            expense_data['payee'] = groups[2] if groups[2] else 'Desconocido'
        
        elif pattern.startswith(r'^\$?'):
            # Patrón: "$25 comida Walmart"
            expense_data['amount'] = self._parse_amount(groups[0])
            expense_data['category'] = self._normalize_category(groups[1])
            expense_data['payee'] = groups[2] if groups[2] else 'Desconocido'
        
        elif 'pesos' in pattern:
            # Patrón: "50 pesos comida"
            expense_data['amount'] = self._parse_amount(groups[0])
            expense_data['category'] = self._normalize_category(groups[1])
            expense_data['payee'] = 'Desconocido'
        
        elif 'compr' in pattern:
            # Patrón: "Compré comida por $30 en Walmart"
            expense_data['amount'] = self._parse_amount(groups[1])
            expense_data['category'] = self._normalize_category(groups[0])
            expense_data['payee'] = groups[2] if groups[2] else 'Desconocido'
        
        return expense_data
    
    def _parse_amount(self, amount_str: str) -> float:
        """Convierte string de cantidad a float (formato colombiano)"""
        if not amount_str:
            return 0.0
        
        # Limpiar el string
        amount_str = amount_str.strip()
        
        # Manejar formato colombiano: separadores de miles con punto y decimales con coma
        # Ejemplos: "40000", "40000,56", "1.000.000", "1.000.000,50"
        
        # Si tiene coma, separar parte entera y decimal
        if ',' in amount_str:
            integer_part, decimal_part = amount_str.split(',', 1)
            # Remover puntos de separadores de miles
            integer_part = integer_part.replace('.', '')
            # Validar que la parte decimal tenga máximo 2 dígitos
            if len(decimal_part) > 2:
                decimal_part = decimal_part[:2]
            amount_str = f"{integer_part}.{decimal_part}"
        else:
            # Solo parte entera, remover separadores de miles
            amount_str = amount_str.replace('.', '')
        
        try:
            return float(amount_str)
        except ValueError:
            return 0.0
    
    def _normalize_category(self, category_str: str) -> str:
        """Normaliza el nombre de la categoría"""
        if not category_str:
            return 'Sin categoría'
        
        category_str = category_str.strip().lower()
        
        # Buscar en el mapeo de categorías
        for main_category, keywords in self.category_mapping.items():
            for keyword in keywords:
                if keyword in category_str:
                    return main_category.title()
        
        # Si no encuentra coincidencia, devolver la categoría original capitalizada
        return category_str.title()
    
    def get_expense_examples(self) -> List[str]:
        """Devuelve ejemplos de formatos de mensaje válidos"""
        return [
            "Gasté $40000 en comida en Éxito",
            "Gasté 25000 pesos en transporte",
            "$30000,50 comida Carulla",
            "45000 pesos gasolina",
            "Compré ropa por $80000 en Falabella",
            "15000,75 entretenimiento Netflix",
            "$1.200.000 arriendo apartamento",
            "500000,25 pesos servicios públicos"
        ]
