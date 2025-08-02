import requests
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Cargar variables de entorno desde config/
config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
load_dotenv(config_path)

class YNABClient:
    """Cliente para interactuar con la API de YNAB"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.ynab.com/v1"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_budgets(self) -> List[Dict]:
        """Obtiene todos los presupuestos disponibles"""
        try:
            response = requests.get(f"{self.base_url}/budgets", headers=self.headers)
            response.raise_for_status()
            return response.json()["data"]["budgets"]
        except requests.exceptions.RequestException as e:
            print(f"Error obteniendo presupuestos: {e}")
            return []
    
    def get_accounts(self, budget_id: str) -> List[Dict]:
        """Obtiene todas las cuentas de un presupuesto"""
        try:
            response = requests.get(f"{self.base_url}/budgets/{budget_id}/accounts", headers=self.headers)
            response.raise_for_status()
            return response.json()["data"]["accounts"]
        except requests.exceptions.RequestException as e:
            print(f"Error obteniendo cuentas: {e}")
            return []
    
    def get_categories(self, budget_id: str) -> List[Dict]:
        """Obtiene todas las categorías de un presupuesto"""
        try:
            response = requests.get(f"{self.base_url}/budgets/{budget_id}/categories", headers=self.headers)
            response.raise_for_status()
            categories = []
            for group in response.json()["data"]["category_groups"]:
                for category in group["categories"]:
                    if not category["deleted"]:
                        categories.append({
                            "id": category["id"],
                            "name": category["name"],
                            "group_name": group["name"]
                        })
            return categories
        except requests.exceptions.RequestException as e:
            print(f"Error obteniendo categorías: {e}")
            return []
    
    def create_transaction(self, budget_id: str, account_id: str, category_id: str, 
                          payee_name: str, amount: float, memo: str = "") -> bool:
        """Crea una nueva transacción en YNAB"""
        try:
            # YNAB usa miliunidades (multiplicar por 1000)
            amount_milliunits = int(amount * -1000)  # Negativo para gastos
            

            
            # Preparar datos de transacción
            transaction_data = {
                "transaction": {
                    "account_id": account_id,
                    "payee_name": payee_name,
                    "amount": amount_milliunits,
                    "memo": memo,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "cleared": "uncleared"
                }
            }
            
            # Solo agregar category_id si no es None o vacío
            if category_id and category_id.strip():
                transaction_data["transaction"]["category_id"] = category_id
            
            response = requests.post(
                f"{self.base_url}/budgets/{budget_id}/transactions",
                headers=self.headers,
                json=transaction_data
            )
            
            if response.status_code == 200 or response.status_code == 201:
                return True
            else:
                print(f"Error YNAB HTTP {response.status_code}: {response.text}")
                response.raise_for_status()
                return False
            
        except requests.exceptions.RequestException as e:
            print(f"Error creando transacción: {e}")
            return False
    
    def find_category_by_name(self, budget_id: str, category_name: str) -> Optional[str]:
        """Busca una categoría por nombre (búsqueda flexible)"""
        categories = self.get_categories(budget_id)
        category_name_lower = category_name.lower()
        
        # Búsqueda exacta
        for category in categories:
            if category["name"].lower() == category_name_lower:
                return category["id"]
        
        # Búsqueda parcial
        for category in categories:
            if category_name_lower in category["name"].lower():
                return category["id"]
        
        return None
    
    def find_account_by_name(self, budget_id: str, account_name: str) -> Optional[str]:
        """Busca una cuenta por nombre"""
        accounts = self.get_accounts(budget_id)
        account_name_lower = account_name.lower()
        
        for account in accounts:
            if account["name"].lower() == account_name_lower or account_name_lower in account["name"].lower():
                return account["id"]
        
        return None
