#!/usr/bin/env python3
"""
YNAB Telegram Bot - Punto de entrada principal
Bot inteligente para registrar gastos en YNAB usando IA y speech-to-text
"""

import sys
import os

# Agregar el directorio src al path para importaciones
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Ahora podemos importar usando paths absolutos
from bot.telegram_bot import YNABTelegramBot

def main():
    """Función principal para iniciar el bot"""
    try:
        bot = YNABTelegramBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario")
    except Exception as e:
        print(f"❌ Error iniciando el bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
