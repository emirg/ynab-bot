import os
import logging
from typing import Dict, List, Optional, Tuple
from integrations.ynab_client import YNABClient

logger = logging.getLogger(__name__)


class YNABCategoryManager:
    """Maneja las categorías reales del presupuesto YNAB del usuario"""
    
    def __init__(self, ynab_client: YNABClient):
        self.ynab_client = ynab_client
        self.categories_cache = {}
        self.category_keywords = {}
        
    def load_categories(self, budget_id: str) -> bool:
        """
        Carga las categorías del presupuesto YNAB y crea mapeo de palabras clave
        
        Args:
            budget_id: ID del presupuesto YNAB
            
        Returns:
            True si se cargaron exitosamente, False si hubo error
        """
        try:
            categories = self.ynab_client.get_categories(budget_id)
            
            if not categories:
                logger.error("No se pudieron obtener categorías de YNAB")
                return False
            
            # Limpiar cache
            self.categories_cache = {}
            self.category_keywords = {}
            
            # Procesar categorías
            for category in categories:
                category_id = category['id']
                category_name = category['name']
                group_name = category['group_name']
                
                # Guardar en cache
                self.categories_cache[category_id] = {
                    'name': category_name,
                    'group': group_name,
                    'full_name': f"{group_name} - {category_name}"
                }
                
                # Crear palabras clave para búsqueda
                keywords = self._generate_keywords(category_name, group_name)
                for keyword in keywords:
                    if keyword not in self.category_keywords:
                        self.category_keywords[keyword] = []
                    self.category_keywords[keyword].append({
                        'id': category_id,
                        'name': category_name,
                        'group': group_name,
                        'score': self._calculate_keyword_score(keyword, category_name)
                    })
            
            logger.info(f"Cargadas {len(self.categories_cache)} categorías de YNAB")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando categorías de YNAB: {e}")
            return False
    
    def _generate_keywords(self, category_name: str, group_name: str) -> List[str]:
        """
        Genera palabras clave para una categoría
        
        Args:
            category_name: Nombre de la categoría
            group_name: Nombre del grupo
            
        Returns:
            Lista de palabras clave
        """
        keywords = []
        
        # Palabras del nombre de la categoría
        category_words = category_name.lower().split()
        keywords.extend(category_words)
        
        # Palabras del grupo
        group_words = group_name.lower().split()
        keywords.extend(group_words)
        
        # Nombre completo
        keywords.append(category_name.lower())
        keywords.append(group_name.lower())
        
        # Mapeo de palabras comunes a categorías específicas
        keyword_mapping = {
            # Transporte
            'uber': ['transporte', 'taxi', 'rideshare'],
            'taxi': ['transporte', 'uber', 'rideshare'],
            'gasolina': ['transporte', 'combustible', 'gas'],
            'combustible': ['transporte', 'gasolina', 'gas'],
            'bus': ['transporte', 'público'],
            'metro': ['transporte', 'público'],
            
            # Comida
            'comida': ['alimentación', 'groceries', 'supermercado', 'mercado'],
            'supermercado': ['comida', 'groceries', 'mercado', 'alimentación'],
            'mercado': ['comida', 'supermercado', 'groceries'],
            'groceries': ['comida', 'supermercado', 'mercado'],
            'éxito': ['supermercado', 'comida', 'groceries'],
            'carulla': ['supermercado', 'comida', 'groceries'],
            'olimpica': ['supermercado', 'comida', 'groceries'],
            
            # Restaurantes
            'restaurante': ['comida', 'dining', 'eating'],
            'mcdonalds': ['restaurante', 'comida rápida'],
            'kfc': ['restaurante', 'comida rápida'],
            'subway': ['restaurante', 'comida rápida'],
            
            # Entretenimiento
            'netflix': ['entretenimiento', 'streaming'],
            'spotify': ['entretenimiento', 'música', 'streaming'],
            'cine': ['entretenimiento', 'movies'],
            'juegos': ['entretenimiento', 'gaming'],
            
            # Servicios
            'internet': ['servicios', 'utilities'],
            'teléfono': ['servicios', 'utilities'],
            'luz': ['servicios', 'utilities', 'electricidad'],
            'agua': ['servicios', 'utilities'],
            
            # Salud
            'farmacia': ['salud', 'medicina'],
            'droguería': ['salud', 'medicina', 'farmacia'],
            'doctor': ['salud', 'médico'],
            'hospital': ['salud', 'médico'],
            
            # Ropa
            'zara': ['ropa', 'clothing'],
            'falabella': ['ropa', 'clothing'],
            'vestimenta': ['ropa', 'clothing'],
            'zapatos': ['ropa', 'clothing']
        }
        
        # Agregar palabras relacionadas
        for word in category_words + group_words:
            if word in keyword_mapping:
                keywords.extend(keyword_mapping[word])
        
        # Remover duplicados y vacíos
        keywords = list(set([k.strip() for k in keywords if k.strip()]))
        
        return keywords
    
    def _calculate_keyword_score(self, keyword: str, category_name: str) -> float:
        """
        Calcula el score de relevancia de una palabra clave para una categoría
        
        Args:
            keyword: Palabra clave
            category_name: Nombre de la categoría
            
        Returns:
            Score entre 0.0 y 1.0
        """
        category_lower = category_name.lower()
        keyword_lower = keyword.lower()
        
        # Score máximo si es el nombre exacto
        if keyword_lower == category_lower:
            return 1.0
        
        # Score alto si está contenido en el nombre
        if keyword_lower in category_lower:
            return 0.8
        
        # Score medio si el nombre está contenido en la palabra clave
        if category_lower in keyword_lower:
            return 0.6
        
        # Score base para palabras relacionadas
        return 0.4
    
    def find_best_category(self, text: str) -> Optional[Tuple[str, str, float]]:
        """
        Encuentra la mejor categoría para un texto dado
        
        Args:
            text: Texto a analizar (descripción del gasto)
            
        Returns:
            Tupla (category_id, category_name, confidence) o None si no encuentra
        """
        if not self.category_keywords:
            logger.warning("Categorías no cargadas. Llama load_categories() primero.")
            return None
        
        text_lower = text.lower()
        matches = []
        
        # Buscar coincidencias de palabras clave
        for keyword, categories in self.category_keywords.items():
            if keyword in text_lower:
                for category_info in categories:
                    # Calcular score basado en la relevancia de la palabra clave
                    # y qué tan bien coincide en el texto
                    keyword_score = category_info['score']
                    
                    # Bonus si es una palabra completa (no parte de otra palabra)
                    import re
                    if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                        keyword_score += 0.2
                    
                    matches.append({
                        'id': category_info['id'],
                        'name': category_info['name'],
                        'group': category_info['group'],
                        'score': keyword_score,
                        'keyword': keyword
                    })
        
        if not matches:
            return None
        
        # Agrupar por categoría y sumar scores
        category_scores = {}
        for match in matches:
            cat_id = match['id']
            if cat_id not in category_scores:
                category_scores[cat_id] = {
                    'name': match['name'],
                    'group': match['group'],
                    'total_score': 0,
                    'matches': []
                }
            category_scores[cat_id]['total_score'] += match['score']
            category_scores[cat_id]['matches'].append(match['keyword'])
        
        # Encontrar la categoría con mayor score
        best_category = max(category_scores.items(), key=lambda x: x[1]['total_score'])
        category_id = best_category[0]
        category_data = best_category[1]
        
        # Normalizar confianza (0-1)
        confidence = min(1.0, category_data['total_score'] / 2.0)
        
        logger.info(f"Categoría encontrada: {category_data['name']} "
                   f"(confianza: {confidence:.2f}, keywords: {category_data['matches']})")
        
        return category_id, category_data['name'], confidence
    
    def get_categories_list(self) -> List[Dict]:
        """
        Devuelve la lista de todas las categorías disponibles
        
        Returns:
            Lista de diccionarios con información de categorías
        """
        return [
            {
                'id': cat_id,
                'name': cat_info['name'],
                'group': cat_info['group'],
                'full_name': cat_info['full_name']
            }
            for cat_id, cat_info in self.categories_cache.items()
        ]
    
    def get_category_by_id(self, category_id: str) -> Optional[Dict]:
        """
        Obtiene información de una categoría por su ID
        
        Args:
            category_id: ID de la categoría
            
        Returns:
            Diccionario con información de la categoría o None
        """
        return self.categories_cache.get(category_id)


if __name__ == "__main__":
    # Script de prueba
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
    if not ynab_token:
        print("Error: YNAB_ACCESS_TOKEN no configurado")
        exit(1)
    
    ynab_client = YNABClient(ynab_token)
    category_manager = YNABCategoryManager(ynab_client)
    
    # Obtener presupuestos
    budgets = ynab_client.get_budgets()
    if not budgets:
        print("Error: No se pudieron obtener presupuestos")
        exit(1)
    
    budget_id = budgets[0]['id']
    print(f"Usando presupuesto: {budgets[0]['name']}")
    
    # Cargar categorías
    if category_manager.load_categories(budget_id):
        print(f"\n✅ Categorías cargadas exitosamente")
        
        # Mostrar algunas categorías
        categories = category_manager.get_categories_list()
        print(f"\nCategorías disponibles ({len(categories)}):")
        for cat in categories[:10]:  # Mostrar solo las primeras 10
            print(f"  - {cat['full_name']}")
        
        if len(categories) > 10:
            print(f"  ... y {len(categories) - 10} más")
        
        # Probar búsqueda de categorías
        test_cases = [
            "comida en éxito",
            "uber al aeropuerto",
            "netflix mensual",
            "gasolina en esso",
            "almuerzo en mcdonalds"
        ]
        
        print(f"\n🧪 Probando búsqueda de categorías:")
        for test in test_cases:
            result = category_manager.find_best_category(test)
            if result:
                cat_id, cat_name, confidence = result
                print(f"  '{test}' → {cat_name} (confianza: {confidence:.2f})")
            else:
                print(f"  '{test}' → No encontrada")
    
    else:
        print("❌ Error cargando categorías")
