#!/usr/bin/env python3
"""
Setup script para YNAB Telegram Bot
Configura el proyecto después de la reorganización
"""

import os
import shutil
from pathlib import Path

def setup_project():
    """Configura el proyecto con la nueva estructura"""
    print("🔧 Configurando YNAB Telegram Bot...")
    
    # Verificar que existen los directorios necesarios
    required_dirs = ['src', 'data', 'config', 'docs']
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"✅ Creado directorio: {dir_name}")
    
    # Verificar archivos de configuración
    if not os.path.exists('config/.env'):
        if os.path.exists('config/.env.example'):
            print("⚠️  Archivo .env no encontrado. Copia config/.env.example a config/.env y configúralo.")
        else:
            print("❌ Archivo .env.example no encontrado.")
    
    # Verificar archivo de datos
    if not os.path.exists('data/category_learning_data.json'):
        # Crear archivo de datos vacío
        empty_data = {
            "payee_category_mapping": {},
            "category_confidence": {},
            "last_updated": {},
            "user_corrections": [],
            "statistics": {
                "total_transactions": 0,
                "learned_associations": 0,
                "accuracy_improvements": 0
            }
        }
        import json
        with open('data/category_learning_data.json', 'w', encoding='utf-8') as f:
            json.dump(empty_data, f, indent=2, ensure_ascii=False)
        print("✅ Creado archivo de datos de aprendizaje")
    
    print("🎉 ¡Configuración completada!")
    print("\n📋 Próximos pasos:")
    print("1. Configura config/.env con tus tokens")
    print("2. Ejecuta: python main.py")

if __name__ == "__main__":
    setup_project()
