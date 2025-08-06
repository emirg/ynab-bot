#!/usr/bin/env python3
"""
YNAB Telegram Bot - Punto de entrada principal
Bot inteligente para registrar gastos en YNAB usando IA y speech-to-text
"""

import sys
import os
import logging

# Configurar logging antes de importar módulos
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Agregar el directorio src al path para importaciones
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Importar la nueva arquitectura
from infrastructure.container import create_container
from presentation.telegram.bot import YNABTelegramBot


def main():
    """Función principal para iniciar el bot con arquitectura en capas"""
    try:
        logger.info("Iniciando YNAB Telegram Bot con arquitectura en capas...")
        
        # Crear contenedor de dependencias
        container = create_container('config/.env')
        
        # Crear e inicializar el bot
        bot = YNABTelegramBot(container)
        
        # Ejecutar el bot
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario")
        print("\n🛑 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"Error crítico iniciando el bot: {e}", exc_info=True)
        print(f"❌ Error iniciando el bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
