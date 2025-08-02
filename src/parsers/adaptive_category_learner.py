import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class AdaptiveCategoryLearner:
    """
    Sistema de aprendizaje adaptativo para mapeo de categorías por lugar/comercio
    
    Aprende de las asociaciones históricas entre payees y categorías para mejorar
    la precisión de futuras predicciones automáticamente.
    """
    
    def __init__(self, data_file: str = None):
        if data_file is None:
            # Usar la nueva ubicación en el directorio data/
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_file = os.path.join(base_dir, "data", "category_learning_data.json")
        self.data_file = data_file
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
        self.load_learning_data()
    
    def load_learning_data(self):
        """Carga los datos de aprendizaje desde archivo"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.learning_data = json.load(f)
                logger.info(f"Datos de aprendizaje cargados: {len(self.learning_data['payee_category_mapping'])} asociaciones")
            else:
                logger.info("Archivo de aprendizaje no existe, iniciando con datos vacíos")
        except Exception as e:
            logger.error(f"Error cargando datos de aprendizaje: {e}")
    
    def _save_data(self):
        """Guarda los datos de aprendizaje en el archivo JSON"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.learning_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Datos de aprendizaje guardados en {self.data_file}")
        except Exception as e:
            logger.error(f"Error guardando datos de aprendizaje: {e}")
    
    def save_learning_data(self):
        """Guarda los datos de aprendizaje a archivo"""
        self._save_data()
    
    def normalize_payee(self, payee: str) -> str:
        """Normaliza el nombre del comercio para consistencia"""
        if not payee:
            return "unknown"
        
        # Convertir a minúsculas y limpiar
        normalized = payee.lower().strip()
        
        # Remover caracteres especiales comunes
        normalized = normalized.replace("'", "").replace('"', "")
        normalized = normalized.replace(".", "").replace(",", "")
        
        # Normalizar nombres comunes de comercios
        normalizations = {
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
        
        # Aplicar normalizaciones
        for canonical, variants in normalizations.items():
            if normalized in variants or any(variant in normalized for variant in variants):
                normalized = canonical
                break
        
        return normalized
    
    def learn_association(self, payee: str, category_id: str, category_name: str, 
                         confidence: float = 1.0, is_correction: bool = False):
        """
        Aprende una nueva asociación payee -> categoría
        
        Args:
            payee: Nombre del comercio/lugar
            category_id: ID de la categoría YNAB
            category_name: Nombre de la categoría
            confidence: Confianza de la asociación (0.0-1.0)
            is_correction: Si es una corrección del usuario
        """
        normalized_payee = self.normalize_payee(payee)
        
        # Inicializar estructuras si no existen
        if normalized_payee not in self.learning_data["payee_category_mapping"]:
            self.learning_data["payee_category_mapping"][normalized_payee] = {}
        
        # Incrementar contador para esta asociación
        mapping = self.learning_data["payee_category_mapping"][normalized_payee]
        if category_id not in mapping:
            mapping[category_id] = {
                "count": 0,
                "category_name": category_name,
                "total_confidence": 0.0,
                "last_seen": datetime.now().isoformat()
            }
        
        # Actualizar datos
        mapping[category_id]["count"] += 1
        mapping[category_id]["total_confidence"] += confidence
        mapping[category_id]["last_seen"] = datetime.now().isoformat()
        mapping[category_id]["category_name"] = category_name  # Actualizar por si cambió
        
        # Calcular confianza promedio para este payee
        total_transactions = sum(cat["count"] for cat in mapping.values())
        best_category = max(mapping.items(), key=lambda x: x[1]["count"])
        best_confidence = best_category[1]["count"] / total_transactions
        
        self.learning_data["category_confidence"][normalized_payee] = best_confidence
        self.learning_data["last_updated"][normalized_payee] = datetime.now().isoformat()
        
        # Registrar corrección si aplica
        if is_correction:
            self.learning_data["user_corrections"].append({
                "payee": normalized_payee,
                "category_id": category_id,
                "category_name": category_name,
                "timestamp": datetime.now().isoformat()
            })
            self.learning_data["statistics"]["accuracy_improvements"] += 1
        
        # Actualizar estadísticas
        self.learning_data["statistics"]["total_transactions"] += 1
        if total_transactions == 1:  # Nueva asociación aprendida
            self.learning_data["statistics"]["learned_associations"] += 1
        
        logger.info(f"Asociación aprendida: {normalized_payee} -> {category_name} "
                   f"(confianza: {best_confidence:.2f}, transacciones: {total_transactions})")
        
        self.save_learning_data()
    
    def predict_category(self, payee: str) -> Optional[Tuple[str, str, float]]:
        """
        Predice la categoría más probable para un payee
        
        Args:
            payee: Nombre del comercio/lugar
            
        Returns:
            Tupla (category_id, category_name, confidence) o None si no hay predicción
        """
        normalized_payee = self.normalize_payee(payee)
        
        if normalized_payee not in self.learning_data["payee_category_mapping"]:
            return None
        
        mapping = self.learning_data["payee_category_mapping"][normalized_payee]
        if not mapping:
            return None
        
        # Encontrar la categoría con más transacciones
        best_category_id = max(mapping.keys(), key=lambda x: mapping[x]["count"])
        best_category_data = mapping[best_category_id]
        
        # Calcular confianza basada en frecuencia y recencia
        total_transactions = sum(cat["count"] for cat in mapping.values())
        frequency_confidence = best_category_data["count"] / total_transactions
        
        # Bonus por recencia (transacciones recientes tienen más peso)
        try:
            last_seen = datetime.fromisoformat(best_category_data["last_seen"])
            days_ago = (datetime.now() - last_seen).days
            recency_bonus = max(0, 1 - (days_ago / 365))  # Decae en un año
        except:
            recency_bonus = 0
        
        # Confianza final
        final_confidence = min(1.0, frequency_confidence + (recency_bonus * 0.1))
        
        # Solo devolver predicción si tenemos suficiente confianza
        if final_confidence >= 0.6 and best_category_data["count"] >= 2:
            logger.info(f"Predicción para {normalized_payee}: {best_category_data['category_name']} "
                       f"(confianza: {final_confidence:.2f}, transacciones: {best_category_data['count']})")
            
            return (
                best_category_id,
                best_category_data["category_name"],
                final_confidence
            )
        
        return None
    
    def get_payee_history(self, payee: str) -> Dict:
        """Obtiene el historial completo de un payee"""
        normalized_payee = self.normalize_payee(payee)
        
        if normalized_payee not in self.learning_data["payee_category_mapping"]:
            return {}
        
        mapping = self.learning_data["payee_category_mapping"][normalized_payee]
        total_transactions = sum(cat["count"] for cat in mapping.values())
        
        history = {
            "payee": normalized_payee,
            "total_transactions": total_transactions,
            "categories": []
        }
        
        for category_id, data in mapping.items():
            history["categories"].append({
                "category_id": category_id,
                "category_name": data["category_name"],
                "count": data["count"],
                "percentage": (data["count"] / total_transactions) * 100,
                "avg_confidence": data["total_confidence"] / data["count"],
                "last_seen": data["last_seen"]
            })
        
        # Ordenar por frecuencia
        history["categories"].sort(key=lambda x: x["count"], reverse=True)
        
        return history
    
    def get_learning_statistics(self) -> Dict:
        """Obtiene estadísticas del sistema de aprendizaje"""
        stats = self.learning_data["statistics"].copy()
        
        # Calcular estadísticas adicionales
        total_payees = len(self.learning_data["payee_category_mapping"])
        high_confidence_payees = sum(
            1 for conf in self.learning_data["category_confidence"].values() 
            if conf >= 0.8
        )
        
        stats.update({
            "total_payees_learned": total_payees,
            "high_confidence_payees": high_confidence_payees,
            "confidence_rate": (high_confidence_payees / total_payees) if total_payees > 0 else 0,
            "total_corrections": len(self.learning_data["user_corrections"])
        })
        
        return stats
    
    def suggest_similar_payees(self, payee: str, limit: int = 5) -> List[Dict]:
        """Sugiere payees similares basado en nombres"""
        normalized_payee = self.normalize_payee(payee)
        suggestions = []
        
        for learned_payee in self.learning_data["payee_category_mapping"].keys():
            if learned_payee == normalized_payee:
                continue
            
            # Calcular similitud simple basada en palabras comunes
            payee_words = set(normalized_payee.split())
            learned_words = set(learned_payee.split())
            
            if payee_words and learned_words:
                similarity = len(payee_words & learned_words) / len(payee_words | learned_words)
                
                if similarity > 0.3:  # Umbral de similitud
                    history = self.get_payee_history(learned_payee)
                    if history["categories"]:
                        suggestions.append({
                            "payee": learned_payee,
                            "similarity": similarity,
                            "most_common_category": history["categories"][0]["category_name"],
                            "transactions": history["total_transactions"]
                        })
        
        # Ordenar por similitud y limitar resultados
        suggestions.sort(key=lambda x: x["similarity"], reverse=True)
        return suggestions[:limit]
    
    def track_transaction(self, payee: str, category_id: str, category_name: str, 
                         amount: float, memo: str = "", transaction_id: str = None):
        """Registra una transacción reciente para posible corrección"""
        transaction = {
            "id": transaction_id or f"temp_{datetime.now().isoformat()}",
            "payee": payee.lower().strip(),
            "category_id": category_id,
            "category_name": category_name,
            "amount": amount,
            "memo": memo,
            "timestamp": datetime.now().isoformat(),
            "corrected": False
        }
        
        # Mantener solo las últimas 10 transacciones
        if "recent_transactions" not in self.learning_data:
            self.learning_data["recent_transactions"] = []
        
        self.learning_data["recent_transactions"].insert(0, transaction)
        self.learning_data["recent_transactions"] = self.learning_data["recent_transactions"][:10]
        
        self._save_data()
        logger.info(f"📝 Transacción registrada para posible corrección: {payee}")
    
    def get_recent_transactions(self, limit: int = 5) -> List[Dict]:
        """Obtiene las transacciones recientes que pueden ser corregidas"""
        recent = self.learning_data.get("recent_transactions", [])
        return recent[:limit]
    
    def correct_category(self, transaction_id: str, new_category_id: str, 
                        new_category_name: str) -> bool:
        """Corrige la categoría de una transacción y actualiza el aprendizaje"""
        try:
            transactions = self.learning_data.get("recent_transactions", [])
            
            # Buscar la transacción
            transaction = None
            for t in transactions:
                if t["id"] == transaction_id:
                    transaction = t
                    break
            
            if not transaction:
                logger.error(f"Transacción {transaction_id} no encontrada")
                return False
            
            payee = transaction["payee"]
            old_category_id = transaction["category_id"]
            old_category_name = transaction["category_name"]
            
            # Registrar la corrección
            correction = {
                "transaction_id": transaction_id,
                "payee": payee,
                "old_category_id": old_category_id,
                "old_category_name": old_category_name,
                "new_category_id": new_category_id,
                "new_category_name": new_category_name,
                "timestamp": datetime.now().isoformat()
            }
            
            self.learning_data["user_corrections"].append(correction)
            
            # Actualizar el mapeo de categorías
            if payee in self.learning_data["payee_category_mapping"]:
                # Reducir el conteo de la categoría incorrecta
                if old_category_id in self.learning_data["payee_category_mapping"][payee]:
                    old_mapping = self.learning_data["payee_category_mapping"][payee][old_category_id]
                    old_mapping["count"] = max(0, old_mapping["count"] - 1)
                    old_mapping["total_confidence"] = max(0, old_mapping["total_confidence"] - 1)
                    
                    # Si el conteo llega a 0, eliminar la asociación
                    if old_mapping["count"] == 0:
                        del self.learning_data["payee_category_mapping"][payee][old_category_id]
                
                # Aumentar el conteo de la categoría correcta
                if new_category_id not in self.learning_data["payee_category_mapping"][payee]:
                    self.learning_data["payee_category_mapping"][payee][new_category_id] = {
                        "count": 0,
                        "category_name": new_category_name,
                        "total_confidence": 0,
                        "last_seen": datetime.now().isoformat()
                    }
                
                new_mapping = self.learning_data["payee_category_mapping"][payee][new_category_id]
                new_mapping["count"] += 2  # Peso extra por corrección manual
                new_mapping["total_confidence"] += 2
                new_mapping["last_seen"] = datetime.now().isoformat()
                new_mapping["category_name"] = new_category_name
            
            # Marcar la transacción como corregida
            transaction["corrected"] = True
            transaction["corrected_category_id"] = new_category_id
            transaction["corrected_category_name"] = new_category_name
            
            # Actualizar estadísticas
            self.learning_data["statistics"]["accuracy_improvements"] += 1
            self.learning_data["last_updated"][payee] = datetime.now().isoformat()
            
            self._save_data()
            
            logger.info(f"✅ Corrección aplicada: {payee} -> {new_category_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error aplicando corrección: {e}")
            return False


if __name__ == "__main__":
    # Script de prueba
    learner = AdaptiveCategoryLearner("test_learning_data.json")
    
    # Simular algunas transacciones
    test_transactions = [
        ("Home Burguer", "cat_restaurant", "🥗 Meal delivery", 0.9),
        ("Home Burguer", "cat_restaurant", " 🥗 Meal delivery", 0.95),
        ("McDonald's", "cat_restaurant", " 🥗 Meal delivery", 0.9),
        ("Éxito", "cat_groceries", "🛒 Groceries", 0.8),
        ("Carulla", "cat_groceries", "🛒 Groceries", 0.85),
        ("Uber", "cat_transport", "🚙 Rideshare (Uber/Lyft/etc.)", 0.9),
        ("Netflix", "cat_entertainment", "📺Netflix", 0.95),
    ]
    
    print("🧪 Probando sistema de aprendizaje adaptativo:\n")
    
    # Aprender asociaciones
    for payee, cat_id, cat_name, confidence in test_transactions:
        learner.learn_association(payee, cat_id, cat_name, confidence)
    
    # Probar predicciones
    test_payees = ["Home Burguer", "home burger", "McDonald's", "Éxito", "Netflix", "Spotify"]
    
    print("🔮 Predicciones:")
    for payee in test_payees:
        prediction = learner.predict_category(payee)
        if prediction:
            cat_id, cat_name, confidence = prediction
            print(f"  {payee} → {cat_name} (confianza: {confidence:.2f})")
        else:
            print(f"  {payee} → Sin predicción")
    
    # Mostrar estadísticas
    print(f"\n📊 Estadísticas:")
    stats = learner.get_learning_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Limpiar archivo de prueba
    if os.path.exists("test_learning_data.json"):
        os.remove("test_learning_data.json")
