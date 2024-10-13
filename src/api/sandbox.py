import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.api.remote.sb_user import get_user_limits
from src.api.remote.sb_history import get_analysis_history
from src.api.remote.sb_reports import get_report_by_uuid
from src.api.remote.sb_analysis import run_url_analysis as api_run_url_analysis, run_file_analysis as api_run_file_analysis
from src.api.security import check_user_and_api_key, check_user_groups
from src.db.users import db_get_user
from src.lang.director import humanize
from src.api.menu_utils import escape_markdown
from datetime import datetime
import os


async def check_user_access(bot, user_id: int):
    logging.debug(f"Checking access for user {user_id}")
    user = await db_get_user(user_id)
    if not user:
        logging.warning(f"User {user_id} not found")
        return False, humanize("USER_NOT_FOUND")
    if user[4]:
        logging.warning(f"User {user_id} is banned")
        return False, humanize("USER_BANNED")
    if user[5]:
        logging.warning(f"User {user_id} is deleted")
        return False, humanize("USER_DELETED")
    
    api_key, error_message = await check_user_and_api_key(user_id)
    if error_message:
        logging.warning(f"API key error for user {user_id}: {error_message}")
        return False, error_message
    
    logging.debug(f"API Key for user {user_id} (first 5 chars): {api_key[:5]}...")
    
    required_group_ids = os.getenv('REQUIRED_GROUP_IDS', '')
    if not await check_user_groups(bot, user_id, required_group_ids):
        logging.warning(f"User {user_id} not in required groups")
        return False, humanize("NOT_IN_REQUIRED_GROUPS")
    
    return True, api_key

async def sandbox_api_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action_func):
    user_id = update.effective_user.id
    logging.debug(f"User ID: {user_id} requesting sandbox API action: {action_func.__name__}")

    access_granted, result = await check_user_access(context.bot, user_id)
    if not access_granted:
        await update.callback_query.answer(text=result)
        logging.warning(f"Access denied for user {user_id}: {result}")
        return

    logging.debug(f"Access granted for user {user_id}, executing {action_func.__name__}")
    await action_func(update, context, result)

async def run_url_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sandbox_api_action(update, context, _run_url_analysis)

async def run_file_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sandbox_api_action(update, context, _run_file_analysis)

async def get_report_by_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sandbox_api_action(update, context, _get_report)

async def get_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sandbox_api_action(update, context, _show_history)

async def _run_url_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, api_key: str):
    # Здесь нужно запросить URL у пользователя
    await update.callback_query.edit_message_text(humanize("ENTER_URL_TO_ANALYZE"))
    context.user_data['next_action'] = 'run_url_analysis'

async def _run_file_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, api_key: str):
    # Здесь нужно запросить файл у пользователя
    await update.callback_query.edit_message_text(humanize("UPLOAD_FILE_TO_ANALYZE"))
    context.user_data['next_action'] = 'run_file_analysis'

async def _get_report(update: Update, context: ContextTypes.DEFAULT_TYPE, api_key: str):
    from src.api.reports import handle_get_reports_by_uuid
    logging.debug(f"Getting report for user {update.effective_user.id} with API key (first 5 chars): {api_key[:5]}")
    context.user_data['api_key'] = api_key

    # Отправляем сообщение о начале загрузки отчета
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(humanize("REPORT_LOADING"))

    await handle_get_reports_by_uuid(update, context)

async def _show_history(update: Update, context: ContextTypes.DEFAULT_TYPE, api_key: str):
    user_id = update.effective_user.id
    logging.debug(f"User ID: {user_id} requesting history.")
    logging.debug(f"API Key (first 5 chars): {api_key[:5]}...")

    limit = 10
    skip = 0
    logging.debug(f"Fetching analysis history with params: limit={limit}, skip={skip}")
    history = await get_analysis_history(api_key, limit, skip)

    if isinstance(history, dict) and "error" in history:
        await update.callback_query.answer(text=history["error"])
        logging.error(f"Error fetching history: {history['error']}")
        return

    if not isinstance(history, list):
        logging.error(f"Expected history to be a list, but got {type(history)}.")
        await update.callback_query.answer(text=humanize("INVALID_DATA_FORMAT"))
        return

    if not history:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=humanize("NO_ANALYSIS_HISTORY"))
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=humanize("LAST_TEN_REPORTS"))
        
        for analysis in history:
            icon = {
                "No threats detected": "🔵",
                "Suspicious activity": "🟡",
                "Malicious activity": "🔴"
            }.get(analysis.get('verdict', 'Unknown'), "⚪")

            text_message = (
                f"{icon}\u00A0***{escape_markdown(datetime.fromisoformat(analysis.get('date', '')).strftime('%d %B %Y, %H:%M'))}***\n"
                f"📄\u00A0`{analysis.get('name', '')}`\n"
                f"🆔\u00A0`{escape_markdown(analysis.get('uuid', ''))}`\n"
            )
            if analysis.get('tags'):
                text_message += f"🏷️\u00A0\\[***{'***\\] \\[***'.join(escape_markdown(tag) for tag in analysis['tags'])}***\\]"

            if text_message.strip():
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text_message, parse_mode='MarkdownV2')

    keyboard = [
        [InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='sandbox_api')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=humanize("CHOOSE_OPTION"), reply_markup=reply_markup)

async def show_api_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sandbox_api_action(update, context, _show_api_limits)

async def _show_api_limits(update: Update, context: ContextTypes.DEFAULT_TYPE, api_key: str):
    user_id = update.effective_user.id
    api_key, error_message = await check_user_and_api_key(user_id)

    if error_message:
        await update.callback_query.answer(text=error_message)
        return
    limits_message = await get_user_limits(api_key)

    if isinstance(limits_message, dict) and "error" in limits_message:
        await update.callback_query.answer(text=limits_message["error"])
        return
    await update.callback_query.edit_message_text(limits_message)

    keyboard = [
        [InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='sandbox_api')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(humanize("CHOOSE_OPTION"), reply_markup=reply_markup)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    next_action = context.user_data.get('next_action')
    if next_action == 'run_url_analysis':
        url = update.message.text.strip()
        result = await api_run_url_analysis(context.user_data['api_key'], url)
        if 'error' in result:
            await update.message.reply_text(humanize("URL_ANALYSIS_ERROR", error=result['error']))
        else:
            await update.message.reply_text(humanize("URL_ANALYSIS_SUCCESS", uuid=result['uuid']))
    elif next_action == 'get_report':
        uuid = update.message.text.strip()
        result = await get_report_by_uuid(context.user_data['api_key'], uuid)
        if 'error' in result:
            await update.message.reply_text(humanize("GET_REPORT_ERROR", error=result['error']))
        else:
            # Здесь нужно обработать и отформатировать отчет
            await update.message.reply_text(humanize("GET_REPORT_SUCCESS", report=str(result)))
    
    del context.user_data['next_action']
