import logging
from telegram import Update
from telegram.ext import ContextTypes

from presentation.telegram.handlers.base_handler import BaseHandler
from presentation.telegram.formatters import SplitConfigResponseFormatter
from presentation.telegram.keyboards import (
    build_split_panel_keyboard,
    build_split_category_selection_keyboard,
    build_split_group_selection_keyboard,
    build_split_account_selection_keyboard,
    build_split_alias_action_keyboard,
    build_split_ask_alias_keyboard,
)
from presentation.telegram.middleware.auth_middleware import require_authentication

logger = logging.getLogger(__name__)

def get_auth_service(self):
    return self.container.get_authorization_service()

class SplitConfigHandler(BaseHandler):
    """Handler for split configuration commands and callbacks"""

    def __init__(self, container):
        super().__init__(container)
        self.split_service = container.get_split_config_service()
        self.user_service = container.get_user_config_service()

    @require_authentication(get_auth_service)
    async def handle_splitwise_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Entry point for /splitwise command"""
        self.log_handler_start("SplitwiseCommand", update)
        user_id = self.get_user_id(update)
        
        user_config = self.user_service.get_user_config(user_id)
        if not user_config or not user_config.is_configured():
            await self.send_message(update, SplitConfigResponseFormatter.format_no_budget_configured())
            return

        await update.message.reply_text(
            SplitConfigResponseFormatter.format_split_panel(),
            reply_markup=build_split_panel_keyboard(),
            parse_mode='Markdown'
        )
        self.log_handler_success("SplitwiseCommand", update)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route callback data starting with 'split_'"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = self.get_user_id(update)
        
        if data == "split_add_group":
            await self._handle_add_group(query, user_id)
        elif data.startswith("split_select_cat_"):
            category_id = data.replace("split_select_cat_", "")
            await self._handle_select_category(query, user_id, category_id)
        elif data.startswith("split_ask_alias_"):
            category_id = data.replace("split_ask_alias_", "")
            await self._handle_ask_alias(query, user_id, category_id, context)
        elif data == "split_skip_alias":
            await self._handle_skip_alias(query, user_id)
        elif data == "split_view":
            await self._handle_view_config(query, user_id)
        elif data == "split_remove_group":
            await self._handle_remove_group_select(query, user_id)
        elif data.startswith("split_rm_"):
            category_id = data.replace("split_rm_", "")
            await self._handle_remove_group(query, user_id, category_id)
        elif data == "split_set_account":
            await self._handle_set_account_select(query, user_id)
        elif data.startswith("split_select_acc_"):
            account_id = data.replace("split_select_acc_", "")
            await self._handle_select_account(query, user_id, account_id)
        elif data == "split_remove_account":
            await self._handle_remove_account(query, user_id)
        elif data == "split_manage_aliases":
            await self._handle_manage_aliases_select(query, user_id)
        elif data.startswith("split_alias_"):
            category_id = data.replace("split_alias_", "")
            await self._handle_alias_menu(query, user_id, category_id)
        elif data.startswith("split_add_alias_"):
            category_id = data.replace("split_add_alias_", "")
            await self._handle_ask_alias(query, user_id, category_id, context)
        elif data.startswith("split_rma_"):
            # split_rma_{cat_id}_{index}
            parts = data.split("_")
            if len(parts) >= 4:
                category_id = parts[2]
                try:
                    index = int(parts[3])
                    await self._handle_remove_alias_by_index(query, user_id, category_id, index)
                except ValueError:
                    logger.error(f"Invalid alias index in callback: {parts[3]}")
        elif data == "split_back":
            await self._handle_back(query, user_id)

    async def _handle_add_group(self, query, user_id: int):
        try:
            categories = self.split_service.get_available_categories_for_split(user_id)
            await query.edit_message_text(
                "Selecciona la categoría de YNAB para el nuevo grupo Splitwise:",
                reply_markup=build_split_category_selection_keyboard(categories),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error fetching categories for split: {e}")
            await self.send_callback_error(query, "No se pudieron obtener las categorías de YNAB.")

    async def _handle_select_category(self, query, user_id: int, category_id: str):
        try:
            group = self.split_service.add_split_group(user_id, category_id)
            await query.edit_message_text(
                SplitConfigResponseFormatter.format_group_added(group.category_name) + 
                "\n\n¿Quieres agregar un alias (nombre de persona) para este grupo?",
                reply_markup=build_split_ask_alias_keyboard(category_id),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error adding split group: {e}")
            await self.send_callback_error(query, f"Error al agregar grupo: {str(e)}")

    async def _handle_ask_alias(self, query, user_id: int, category_id: str, context: ContextTypes.DEFAULT_TYPE):
        try:
            # We need to find the category name to show in the message
            summary = self.split_service.get_split_config_summary(user_id)
            groups = summary.get("groups", [])
            group = next((g for g in groups if g.category_id == category_id), None)
            category_name = group.category_name if group else ""
            
            context.user_data["pending_alias_category_id"] = category_id
            await query.edit_message_text(
                SplitConfigResponseFormatter.format_ask_alias(category_name),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error in ask alias flow: {e}")
            await self.send_callback_error(query, "Ocurrió un error al iniciar el flujo de alias.")

    async def _handle_skip_alias(self, query, user_id: int):
        await self._handle_back(query, user_id)

    async def _handle_view_config(self, query, user_id: int):
        summary = self.split_service.get_split_config_summary(user_id)
        await query.edit_message_text(
            SplitConfigResponseFormatter.format_split_summary(summary),
            reply_markup=build_split_panel_keyboard(),
            parse_mode='Markdown'
        )

    async def _handle_remove_group_select(self, query, user_id: int):
        summary = self.split_service.get_split_config_summary(user_id)
        groups = summary.get("groups", [])
        if not groups:
            await query.edit_message_text(
                "No tienes grupos configurados.",
                reply_markup=build_split_panel_keyboard(),
                parse_mode='Markdown'
            )
            return

        await query.edit_message_text(
            "Selecciona el grupo a eliminar:",
            reply_markup=build_split_group_selection_keyboard(groups, "rm"),
            parse_mode='Markdown'
        )

    async def _handle_remove_group(self, query, user_id: int, category_id: str):
        try:
            # Get name before deleting
            summary = self.split_service.get_split_config_summary(user_id)
            groups = summary.get("groups", [])
            group = next((g for g in groups if g.category_id == category_id), None)
            name = group.category_name if group else category_id
            
            if self.split_service.remove_split_group(user_id, category_id):
                await self.send_callback_message(query, SplitConfigResponseFormatter.format_group_removed(name))
            
            await self._handle_back(query, user_id)
        except Exception as e:
            logger.error(f"Error removing split group: {e}")
            await self.send_callback_error(query, "Error al eliminar el grupo.")

    async def _handle_set_account_select(self, query, user_id: int):
        try:
            accounts = self.split_service.get_available_accounts_for_split(user_id)
            await query.edit_message_text(
                "Selecciona la cuenta para los gastos compartidos:",
                reply_markup=build_split_account_selection_keyboard(accounts),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error fetching accounts for split: {e}")
            await self.send_callback_error(query, "No se pudieron obtener las cuentas de YNAB.")

    async def _handle_select_account(self, query, user_id: int, account_id: str):
        try:
            config = self.split_service.set_shared_account(user_id, account_id)
            await self.send_callback_message(query, SplitConfigResponseFormatter.format_shared_account_set(config.account_name))
            await self._handle_back(query, user_id)
        except Exception as e:
            logger.error(f"Error setting shared account: {e}")
            await self.send_callback_error(query, f"Error al configurar cuenta: {str(e)}")

    async def _handle_remove_account(self, query, user_id: int):
        try:
            if self.split_service.remove_shared_account(user_id):
                await self.send_callback_message(query, SplitConfigResponseFormatter.format_shared_account_removed())
            await self._handle_back(query, user_id)
        except Exception as e:
            logger.error(f"Error removing shared account: {e}")
            await self.send_callback_error(query, "Error al quitar la cuenta compartida.")

    async def _handle_manage_aliases_select(self, query, user_id: int):
        summary = self.split_service.get_split_config_summary(user_id)
        groups = summary.get("groups", [])
        if not groups:
            await query.edit_message_text(
                "No tienes grupos configurados. Agrega uno primero.",
                reply_markup=build_split_panel_keyboard(),
                parse_mode='Markdown'
            )
            return

        await query.edit_message_text(
            "Selecciona el grupo para gestionar sus aliases:",
            reply_markup=build_split_group_selection_keyboard(groups, "alias"),
            parse_mode='Markdown'
        )

    async def _handle_alias_menu(self, query, user_id: int, category_id: str):
        summary = self.split_service.get_split_config_summary(user_id)
        groups = summary.get("groups", [])
        group = next((g for g in groups if g.category_id == category_id), None)
        if not group:
            await self.send_callback_error(query, "Grupo no encontrado.")
            await self._handle_back(query, user_id)
            return

        await query.edit_message_text(
            f"Gestionando aliases para *{group.category_name}*:",
            reply_markup=build_split_alias_action_keyboard(group),
            parse_mode='Markdown'
        )

    async def _handle_remove_alias_by_index(self, query, user_id: int, category_id: str, index: int):
        try:
            summary = self.split_service.get_split_config_summary(user_id)
            groups = summary.get("groups", [])
            group = next((g for g in groups if g.category_id == category_id), None)
            if not group or index >= len(group.person_aliases):
                await self.send_callback_error(query, "Alias no encontrado.")
                await self._handle_alias_menu(query, user_id, category_id)
                return
            
            alias = group.person_aliases[index]
            if self.split_service.remove_person_alias(user_id, category_id, alias):
                await self.send_callback_message(query, SplitConfigResponseFormatter.format_alias_removed(alias, group.category_name))
            
            await self._handle_alias_menu(query, user_id, category_id)
        except Exception as e:
            logger.error(f"Error removing alias: {e}")
            await self.send_callback_error(query, "Error al eliminar el alias.")

    async def _handle_back(self, query, user_id: int):
        await query.edit_message_text(
            SplitConfigResponseFormatter.format_split_panel(),
            reply_markup=build_split_panel_keyboard(),
            parse_mode='Markdown'
        )

    async def handle_alias_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Processes free-text alias input.
        Returns True if the message was handled as an alias, False otherwise.
        """
        category_id = context.user_data.get("pending_alias_category_id")
        if not category_id:
            return False

        user_id = self.get_user_id(update)
        alias = update.message.text.strip()
        
        if not alias:
            await self.send_message(update, "❌ El nombre no puede estar vacío. Por favor intenta de nuevo:")
            return True

        try:
            # Clear state first to avoid loops on error
            del context.user_data["pending_alias_category_id"]
            
            # Get group name for confirmation
            summary = self.split_service.get_split_config_summary(user_id)
            groups = summary.get("groups", [])
            group = next((g for g in groups if g.category_id == category_id), None)
            category_name = group.category_name if group else category_id

            if self.split_service.add_person_alias(user_id, category_id, alias):
                await self.send_message(update, SplitConfigResponseFormatter.format_alias_added(alias, category_name))
            else:
                await self.send_message(update, f"⚠️ El alias *{alias}* ya existe para este grupo.")
            
            # Show panel again
            await self.send_message(
                update, 
                SplitConfigResponseFormatter.format_split_panel(),
                reply_markup=build_split_panel_keyboard()
            )
            return True
        except Exception as e:
            logger.error(f"Error adding alias from text: {e}")
            await self.send_error_message(update, f"Error al agregar alias: {str(e)}")
            return True

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Standard handler method (routes to command or callback)"""
        if update.callback_query:
            await self.handle_callback_query(update, context)
        elif update.message and update.message.text.startswith('/splitwise'):
            await self.handle_splitwise_command(update, context)
