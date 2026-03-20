#!/usr/bin/env python3
"""
YNAB Telegram Bot - Punto de entrada principal
Bot inteligente para registrar gastos en YNAB usando IA y speech-to-text
"""

import sys
import os

# Agregar el directorio src al path para importaciones (antes de imports locales)
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Configurar logging estructurado (JSON en Railway, texto en local)
from infrastructure.logging_config import setup_logging
setup_logging()

import logging
logger = logging.getLogger(__name__)

# Importar la nueva arquitectura
from infrastructure.container import create_container
from infrastructure.health import start_health_server, set_oauth_service, set_on_oauth_success
from infrastructure.telegram_notifier import TelegramNotifier
from presentation.telegram.bot import YNABTelegramBot
from presentation.telegram.keyboards import budget_keyboard_to_dict
from presentation.telegram.formatters import GeneralResponseFormatter


def main():
    """Función principal para iniciar el bot con arquitectura en capas"""
    try:
        logger.info("Iniciando YNAB Telegram Bot con arquitectura en capas...")

        # Iniciar servidor de health check
        port = int(os.environ.get("PORT", 8080))
        start_health_server(port)

        # Crear contenedor de dependencias
        container = create_container('config/.env')
        config = container.get_config()

        # Conectar OAuth service al health server
        set_oauth_service(container.get_oauth_service())

        # Configurar notificador Telegram para eventos post-OAuth
        notifier = TelegramNotifier(config.telegram_token)
        
        def on_oauth_success(telegram_user_id: int):
            """Callback ejecutado cuando un usuario conecta su cuenta YNAB con éxito"""
            try:
                logger.info(f"Procesando notificación post-OAuth para usuario {telegram_user_id}")
                
                # Obtener presupuestos disponibles
                user_config_service = container.get_user_config_service()
                try:
                    budgets = user_config_service.get_available_budgets(telegram_user_id)
                    keyboard = budget_keyboard_to_dict(budgets)
                    message = GeneralResponseFormatter.format_post_oauth_message()
                    
                    # Enviar mensaje con botones de presupuesto
                    notifier.send_message(
                        chat_id=telegram_user_id,
                        text=message,
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Error obteniendo presupuestos post-OAuth: {e}")
                    # Degradación graciosa: mensaje solo texto
                    fallback_msg = "✅ *¡Cuenta YNAB conectada!* \n\nUsa `/start` para continuar con la configuración de tu presupuesto."
                    notifier.send_message(chat_id=telegram_user_id, text=fallback_msg)
            
            except Exception as e:
                logger.error(f"Error fatal en callback on_oauth_success: {e}")

        # Registrar callback en el servidor health
        set_on_oauth_success(on_oauth_success)

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
