import datetime
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from src.lang.director import humanize
from src.db.api_keys import (
    db_add_api_key, db_get_api_keys, db_delete_api_key, 
    db_change_api_key_name, db_set_active_api_key
)
from src.api.security import check_in_groups
from telegram.constants import ChatType

def create_manage_api_key_menu():
    keyboard = [
        [InlineKeyboardButton(humanize("MENU_BUTTON_SHOW_API_KEYS"), callback_data='show_api_keys')],
        [InlineKeyboardButton(humanize("MENU_BUTTON_ADD_API_KEY"), callback_data='add_api_key')],
        [InlineKeyboardButton(humanize("MENU_BUTTON_DELETE_API_KEY"), callback_data='delete_api_key')],
        [InlineKeyboardButton(humanize("MENU_BUTTON_CHANGE_API_KEY_NAME"), callback_data='change_api_key_name')],
        [InlineKeyboardButton(humanize("MENU_BUTTON_SET_ACTIVE_API_KEY"), callback_data='set_active_api_key')],
        [InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='settings')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def manage_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = humanize("MANAGE_API_KEY_MENU_TEXT")
    reply_markup = create_manage_api_key_menu()
    await update.callback_query.edit_message_text(menu_text, reply_markup=reply_markup)

async def check_access_rights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    required_group_ids = os.getenv('REQUIRED_GROUP_IDS', '')
    
    user_groups = await check_in_groups(context.bot, user_id, is_bot=False, required_group_ids=required_group_ids)
    
    if not user_groups:
        await update.callback_query.answer(humanize("NO_REQUIRED_GROUPS"))
        await update.callback_query.edit_message_text(humanize("NO_REQUIRED_GROUPS"))
        return
    
    keyboard = []
    message_text = humanize("ACCESS_RIGHTS_INFO") + "\n\n"
    
    for group_id, (is_member, chat, bot_is_member) in user_groups.items():
        if chat:
            group_name = chat.title
            status_icon = "✅" if is_member else "❌"
            button_text = f"{status_icon} {group_name}"
            message_text += f"{button_text}\n"
            
            invite_link = chat.invite_link if bot_is_member else None
            if not invite_link and chat.username:
                invite_link = f"https://t.me/{chat.username}"
            elif not invite_link and chat.type == ChatType.SUPERGROUP:
                invite_link = f"https://t.me/c/{str(chat.id)[4:]}"
            
            if invite_link:
                keyboard.append([InlineKeyboardButton(button_text, url=invite_link)])
            else:
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"group_info_{group_id}")])
        else:
            button_text = f"❓ Group {group_id}"
            message_text += f"{button_text}\n"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"group_info_{group_id}")])
    
    if not keyboard:
        message_text += humanize("NO_ACCESSIBLE_GROUPS")
    
    keyboard.append([InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='settings')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)

async def show_api_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    api_keys = await db_get_api_keys(user_id)

    if not api_keys:
        await update.callback_query.answer(text=humanize("NO_API_KEYS_FOUND"))
        return

    keys_text = humanize("YOUR_API_KEYS") + "\n\n"
    for key, name, is_active in api_keys:
        status = "✅ " if is_active else ""
        keys_text += f"{status}{name}: {key[:6]}...{key[-6:]}\n"

    await update.callback_query.message.reply_text(keys_text)

    # Создаем кнопку "Back to Settings"
    keyboard = [
        [InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем кнопку
    await update.callback_query.message.reply_text(humanize("CHOOSE_OPTION"), reply_markup=reply_markup)

async def add_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(humanize("ENTER_NEW_API_KEY_FORMAT"))
    context.user_data['next_action'] = 'add_api_key'

async def delete_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    api_keys = await db_get_api_keys(user_id)
    
    if not api_keys:
        await update.callback_query.answer(humanize("NO_API_KEYS_TO_DELETE"))
        return

    keyboard = []
    for key, name, is_active in api_keys:
        status = "✅ " if is_active else ""
        button_text = f"{status}{name}: {key[:6]}...{key[-6:]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delete_{key}")])
    
    keyboard.append([InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='back_to_manage_api_key')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(humanize("SELECT_API_KEY_TO_DELETE"), reply_markup=reply_markup)

async def change_api_key_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    api_keys = await db_get_api_keys(user_id)
    
    if not api_keys:
        await update.callback_query.answer(humanize("NO_API_KEYS_TO_RENAME"))
        return

    keyboard = []
    for key, name, is_active in api_keys:
        status = "✅ " if is_active else ""
        button_text = f"{status}{name}: {key[:6]}...{key[-6:]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"rename_{key}")])
    
    keyboard.append([InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='back_to_manage_api_key')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(humanize("SELECT_API_KEY_TO_RENAME"), reply_markup=reply_markup)

async def set_active_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    api_keys = await db_get_api_keys(user_id)
    
    if not api_keys:
        await update.callback_query.answer(humanize("NO_API_KEYS_TO_ACTIVATE"))
        return

    keyboard = []
    for key, name, is_active in api_keys:
        status = "✅ " if is_active else ""
        button_text = f"{status}{name}: {key[:6]}...{key[-6:]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"activate_{key}")])
    
    keyboard.append([InlineKeyboardButton(humanize("MENU_BUTTON_BACK"), callback_data='back_to_manage_api_key')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(humanize("SELECT_API_KEY_TO_ACTIVATE"), reply_markup=reply_markup)

async def handle_api_key_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('delete_'):
        api_key = query.data.split('_', 1)[1]
        await db_delete_api_key(update.effective_user.id, api_key)
        await query.edit_message_text(humanize("API_KEY_DELETED"))
        await manage_api_key(update, context)
    elif query.data.startswith('rename_'):
        api_key = query.data.split('_', 1)[1]
        context.user_data['api_key_to_rename'] = api_key
        await query.edit_message_text(humanize("ENTER_NEW_API_KEY_NAME"))
        context.user_data['next_action'] = 'rename_api_key'
    elif query.data.startswith('activate_'):
        api_key = query.data.split('_', 1)[1]
        await db_set_active_api_key(update.effective_user.id, api_key)
        await query.edit_message_text(humanize("API_KEY_ACTIVATED"))
        await manage_api_key(update, context)
    elif query.data == 'back_to_manage_api_key':
        await manage_api_key(update, context)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    next_action = context.user_data.get('next_action')
    if next_action == 'add_api_key':
        user_id = update.effective_user.id
        input_text = update.message.text.strip()
        
        # Разделяем ввод на API ключ и имя ключа
        match = re.match(r'^(\S+)\s*(.*)$', input_text)
        if match:
            new_key = match.group(1)
            key_name = match.group(2).strip()
        else:
            new_key = input_text
            key_name = ""
        
        # Если имя ключа не предоставлено или пустое, генерируем его
        if not key_name:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            key_name = f"New API Key {timestamp}"
        
        # Валидация имени ключа (удаляем недопустимые символы)
        key_name = re.sub(r'[^\w\s-]', '', key_name).strip()
        if not key_name:
            key_name = "Unnamed Key"
        
        success, error_message = await db_add_api_key(user_id, new_key, key_name)
        if success:
            await update.message.reply_text(humanize("API_KEY_ADDED"))
        else:
            if error_message == "API_KEY_ALREADY_EXISTS":
                await update.message.reply_text(humanize("API_KEY_ALREADY_EXISTS"))
            else:
                await update.message.reply_text(humanize("ERROR_ADDING_API_KEY"))
        
        # Отпрвляем новое сообщение с меню
        menu_text = humanize("MANAGE_API_KEY_MENU_TEXT")
        reply_markup = create_manage_api_key_menu()
        await update.message.reply_text(menu_text, reply_markup=reply_markup)
    
    elif next_action == 'rename_api_key':
        user_id = update.effective_user.id
        api_key = context.user_data.get('api_key_to_rename')
        new_name = update.message.text.strip()
        
        # Валидация нового имени ключа
        new_name = re.sub(r'[^\w\s-]', '', new_name).strip()
        if not new_name:
            new_name = "Unnamed Key"
        
        if api_key:
            await db_change_api_key_name(user_id, api_key, new_name)
            await update.message.reply_text(humanize("API_KEY_RENAMED"))
            
            # Отправляем новое сообщение с меню
            menu_text = humanize("MANAGE_API_KEY_MENU_TEXT")
            reply_markup = create_manage_api_key_menu()
            await update.message.reply_text(menu_text, reply_markup=reply_markup)
    
    del context.user_data['next_action']

async def handle_group_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    group_id = query.data.split('_')[-1]
    await query.answer(humanize("GROUP_LINK_NOT_AVAILABLE"))