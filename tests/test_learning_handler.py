import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from presentation.telegram.handlers.learning_handler import LearningHandler
from domain.models.user import UserStatus

@pytest.fixture
def container():
    mock = MagicMock()
    # Setup common services
    auth_service = MagicMock()
    # By default, authorize all users for these tests
    auth_service.get_user_status.return_value = UserStatus.AUTHORIZED
    mock.get_auth_service.return_value = auth_service
    
    # Container.get(LearningService) etc.
    mock.get.side_effect = lambda cls: MagicMock()
    return mock

@pytest.fixture
def handler(container):
    return LearningHandler(container)

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture
def update():
    mock = MagicMock(spec=Update)
    mock.effective_user = MagicMock(spec=User)
    mock.effective_user.id = 123
    mock.effective_user.first_name = "TestUser"
    
    # Message needs to be properly mocked for async calls
    message_mock = AsyncMock(spec=Message)
    message_mock.text = ""
    mock.message = message_mock
    mock.callback_query = None
    return mock

@pytest.fixture
def context():
    mock = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    mock.args = []
    return mock

@pytest.mark.anyio
async def test_handle_learning_dashboard_command(handler, container, update, context):
    # Setup
    learning_service = handler.learning_service
    learning_service.format_learning_dashboard_message.return_value = "Panel content"
    
    # Run
    await handler.handle_learning_dashboard_command(update, context)
    
    # Verify
    learning_service.format_learning_dashboard_message.assert_called_once_with(123)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "Panel content" in args[0]

@pytest.mark.anyio
async def test_handle_forget_command_no_args(handler, update, context):
    # Run
    context.args = []
    await handler.handle_forget_command(update, context)
    
    # Verify
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "Uso del comando /olvidar" in args[0]

@pytest.mark.anyio
async def test_handle_forget_command_with_args(handler, update, context):
    # Setup
    context.args = ["McDonald's"]
    learning_service = handler.learning_service
    learning_service.forget_payee.return_value = True
    learning_service.format_forget_result_message.return_value = "He olvidado McDonald's"
    
    # Run
    await handler.handle_forget_command(update, context)
    
    # Verify
    learning_service.forget_payee.assert_called_once_with(123, "McDonald's")
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "He olvidado McDonald's" in args[0]

# --- /editar handler tests ---

@pytest.mark.anyio
async def test_handle_edit_command_no_args_shows_help(handler, update, context):
    """No args (or only index) → help text is shown."""
    context.args = []
    await handler.handle_edit_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert "editar" in args[0].lower() or "monto" in args[0].lower()


@pytest.mark.anyio
async def test_handle_edit_command_edit_amount(handler, update, context):
    """Edit amount with a plain number."""
    context.args = ['monto', '30000']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': 'McDonalds',
        'changes': {'amount': {'old': 25000, 'new': 30000}},
    }
    await handler.handle_edit_command(update, context)
    handler.expense_service.edit_last_transaction.assert_called_once()
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    # new_amount should be Decimal("30000"), transaction_index 0
    from decimal import Decimal
    assert call_kwargs[0][0] == 123  # user_id
    assert call_kwargs[0][1] == 0   # transaction_index
    assert call_kwargs[0][2] == Decimal("30000")  # new_amount
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'McDonalds' in args[0] or 'actualizada' in args[0].lower()


@pytest.mark.anyio
async def test_handle_edit_command_edit_amount_mil_suffix(handler, update, context):
    """Edit amount with mil suffix."""
    context.args = ['monto', '40mil']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': 'Supermercado',
        'changes': {'amount': {'old': 10000, 'new': 40000}},
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    from decimal import Decimal
    assert call_kwargs[0][2] == Decimal("40000")


@pytest.mark.anyio
async def test_handle_edit_command_edit_amount_k_suffix(handler, update, context):
    """Edit amount with k suffix."""
    context.args = ['monto', '40k']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': 'Tienda',
        'changes': {'amount': {'old': 10000, 'new': 40000}},
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    from decimal import Decimal
    assert call_kwargs[0][2] == Decimal("40000")


@pytest.mark.anyio
async def test_handle_edit_command_edit_amount_comma_decimal(handler, update, context):
    """Edit amount with comma as decimal separator."""
    context.args = ['monto', '1,5']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': 'Cafe',
        'changes': {'amount': {'old': 1000, 'new': 1500}},
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    from decimal import Decimal
    assert call_kwargs[0][2] == Decimal("1.5")


@pytest.mark.anyio
async def test_handle_edit_command_invalid_amount(handler, update, context):
    """Invalid amount format → error message shown, service not called."""
    context.args = ['monto', 'abc']
    await handler.handle_edit_command(update, context)
    handler.expense_service.edit_last_transaction.assert_not_called()
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'invalido' in args[0].lower() or 'Monto' in args[0]


@pytest.mark.anyio
async def test_handle_edit_command_edit_payee(handler, update, context):
    """Edit payee (comercio) with multi-word value."""
    context.args = ['comercio', "McDonald's", 'Argentina']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': "McDonald's Argentina",
        'changes': {'payee': {'old': 'Mc', 'new': "McDonald's Argentina"}},
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    assert call_kwargs[0][3] == "McDonald's Argentina"  # new_payee
    update.message.reply_text.assert_called_once()


@pytest.mark.anyio
async def test_handle_edit_command_edit_category(handler, update, context):
    """Edit category with fuzzy match returning success."""
    context.args = ['categoria', 'Restaurantes']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': 'McDonalds',
        'changes': {'category': {'old': 'Comida rapida', 'new': 'Restaurantes'}},
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    assert call_kwargs[0][4] == 'Restaurantes'  # new_category
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'Restaurantes' in args[0]


@pytest.mark.anyio
async def test_handle_edit_command_edit_account(handler, update, context):
    """Edit account (cuenta)."""
    context.args = ['cuenta', 'Tarjeta', 'de', 'credito']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': 'McDonalds',
        'changes': {'account': {'new': 'Tarjeta de credito'}},
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    assert call_kwargs[0][5] == 'Tarjeta de credito'  # new_account
    update.message.reply_text.assert_called_once()


@pytest.mark.anyio
async def test_handle_edit_command_edit_multiple_fields(handler, update, context):
    """Edit multiple fields in one command."""
    context.args = ['monto', '30000', 'comercio', "McDonald's", 'categoria', 'Restaurantes']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': "McDonald's",
        'changes': {
            'amount': {'old': 25000, 'new': 30000},
            'payee': {'old': 'Mc', 'new': "McDonald's"},
            'category': {'old': 'Otro', 'new': 'Restaurantes'},
        },
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    from decimal import Decimal
    assert call_kwargs[0][2] == Decimal("30000")
    assert call_kwargs[0][3] == "McDonald's"
    assert call_kwargs[0][4] == "Restaurantes"
    update.message.reply_text.assert_called_once()


@pytest.mark.anyio
async def test_handle_edit_command_with_index(handler, update, context):
    """First numeric arg is consumed as 1-based transaction index."""
    context.args = ['3', 'categoria', 'Restaurantes']
    handler.expense_service.edit_last_transaction.return_value = {
        'payee': 'Cafe',
        'changes': {'category': {'old': 'Otro', 'new': 'Restaurantes'}},
    }
    await handler.handle_edit_command(update, context)
    call_kwargs = handler.expense_service.edit_last_transaction.call_args
    assert call_kwargs[0][1] == 2  # 3 - 1 = 2 (0-based)
    assert call_kwargs[0][4] == 'Restaurantes'


@pytest.mark.anyio
async def test_handle_edit_command_category_not_found(handler, update, context):
    """Category not found error is handled correctly."""
    context.args = ['categoria', 'NombreInexistente']
    handler.expense_service.edit_last_transaction.return_value = {
        'error': 'category_not_found',
        'message': "No encontre una categoria que coincida con 'NombreInexistente'.",
    }
    await handler.handle_edit_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'NombreInexistente' in args[0] or 'categoria' in args[0].lower()


@pytest.mark.anyio
async def test_handle_edit_command_account_not_found(handler, update, context):
    """Account not found error is handled correctly."""
    context.args = ['cuenta', 'CuentaFalsa']
    handler.expense_service.edit_last_transaction.return_value = {
        'error': 'account_not_found',
        'message': "No encontre una cuenta que coincida con 'CuentaFalsa'.",
    }
    await handler.handle_edit_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'CuentaFalsa' in args[0] or 'cuenta' in args[0].lower()


@pytest.mark.anyio
async def test_handle_edit_command_time_window_error(handler, update, context):
    """Time window error uses formatter message."""
    context.args = ['monto', '10000']
    handler.expense_service.edit_last_transaction.return_value = {
        'error': 'time_window_exceeded',
    }
    await handler.handle_edit_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'minutos' in args[0].lower() or '5' in args[0]


@pytest.mark.anyio
async def test_handle_edit_command_no_recent_transactions(handler, update, context):
    """No recent transactions error uses formatter message."""
    context.args = ['monto', '10000']
    handler.expense_service.edit_last_transaction.return_value = {
        'error': 'no_recent_transactions',
    }
    await handler.handle_edit_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'transacciones' in args[0].lower() or 'modificar' in args[0].lower()


@pytest.mark.anyio
async def test_handle_edit_command_index_out_of_range(handler, update, context):
    """Index out of range error is handled."""
    context.args = ['99', 'monto', '10000']
    handler.expense_service.edit_last_transaction.return_value = {
        'error': 'index_out_of_range',
    }
    await handler.handle_edit_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'rango' in args[0].lower() or 'indice' in args[0].lower()


@pytest.mark.anyio
async def test_handle_edit_command_service_returns_none(handler, update, context):
    """Service returns None → generic error message."""
    context.args = ['monto', '10000']
    handler.expense_service.edit_last_transaction.return_value = None
    await handler.handle_edit_command(update, context)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'No se pudo' in args[0] or 'editar' in args[0].lower()

@pytest.mark.anyio
async def test_handle_routing_aprendizaje(handler, update, context):
    # Setup
    update.message.text = "/aprendizaje"
    handler.handle_learning_dashboard_command = AsyncMock()
    
    # Run
    await handler.handle(update, context)
    
    # Verify
    handler.handle_learning_dashboard_command.assert_called_once_with(update, context)

@pytest.mark.anyio
async def test_handle_routing_olvidar(handler, update, context):
    # Setup
    update.message.text = "/olvidar McDonald's"
    handler.handle_forget_command = AsyncMock()

    # Run
    await handler.handle(update, context)

    # Verify
    handler.handle_forget_command.assert_called_once_with(update, context)


# --- /deshacer handler tests ---

@pytest.mark.anyio
async def test_handle_undo_command_success(handler, update, context):
    """Successful undo returns a confirmation message with payee, amount, category."""
    handler.expense_service.undo_last_transaction.return_value = {
        'payee': 'McDonalds',
        'amount': 25000,
        'category_name': 'Restaurantes',
    }

    await handler.handle_undo_command(update, context)

    handler.expense_service.undo_last_transaction.assert_called_once_with(123)
    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'McDonalds' in args[0]
    assert 'Restaurantes' in args[0]


@pytest.mark.anyio
async def test_handle_undo_command_no_recent_transactions(handler, update, context):
    """Service returns no_recent_transactions error → formatter message shown."""
    handler.expense_service.undo_last_transaction.return_value = {
        'error': 'no_recent_transactions',
    }

    await handler.handle_undo_command(update, context)

    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    # Should use format_no_recent_transaction_error() message
    assert 'transacciones recientes' in args[0].lower() or 'modificar' in args[0].lower()


@pytest.mark.anyio
async def test_handle_undo_command_time_window_error(handler, update, context):
    """Service returns time_window_exceeded error → formatter message shown."""
    handler.expense_service.undo_last_transaction.return_value = {
        'error': 'time_window_exceeded',
    }

    await handler.handle_undo_command(update, context)

    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    # Should use format_time_window_error() message
    assert 'minutos' in args[0].lower() or '5 minutos' in args[0] or 'modificar' in args[0].lower()


@pytest.mark.anyio
async def test_handle_undo_command_other_error(handler, update, context):
    """Service returns an unrecognized error code → it is shown directly."""
    handler.expense_service.undo_last_transaction.return_value = {
        'error': 'no_ynab_transaction_id',
    }

    await handler.handle_undo_command(update, context)

    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'no_ynab_transaction_id' in args[0]


@pytest.mark.anyio
async def test_handle_undo_command_ynab_failure(handler, update, context):
    """Service returns None (unexpected failure) → generic error message shown."""
    handler.expense_service.undo_last_transaction.return_value = None

    await handler.handle_undo_command(update, context)

    update.message.reply_text.assert_called_once()
    args, _ = update.message.reply_text.call_args
    assert 'No se pudo' in args[0] or 'deshacer' in args[0].lower()


@pytest.mark.anyio
async def test_handle_routing_deshacer(handler, update, context):
    """/deshacer is routed to handle_undo_command."""
    update.message.text = "/deshacer"
    handler.handle_undo_command = AsyncMock()

    await handler.handle(update, context)

    handler.handle_undo_command.assert_called_once_with(update, context)


@pytest.mark.anyio
async def test_handle_routing_editar(handler, update, context):
    """/editar is routed to handle_edit_command."""
    update.message.text = "/editar monto 10000"
    handler.handle_edit_command = AsyncMock()

    await handler.handle(update, context)

    handler.handle_edit_command.assert_called_once_with(update, context)
