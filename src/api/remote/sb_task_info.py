from enum import Enum
from datetime import datetime
import logging
from src.api.menu_utils import escape_markdown
from dateutil import parser

class ResultType(Enum):
    TEXT = "text"
    IMAGE = "image"

def process_task_info(verdict, date, main_object, uuid, tags, status, result_type: ResultType):
    if result_type == ResultType.IMAGE:
        return None
    elif result_type == ResultType.TEXT:
        return process_task_info_text(verdict, date, main_object, uuid, tags, status)
    else:
        logging.error(f"Unknown result type: {result_type}")
        return None

def process_task_info_text(verdict, date, main_object, uuid, tags, status):
    verdict_icon = {
        "No threats detected": "🔵",
        "Suspicious activity": "🟡",
        "Malicious activity": "🔴",
        0: "🔵",
        1: "🟡",
        2: "🔴"
    }.get(verdict, "⚪")

    status_icon = {
        "queued": "⏳",
        "running": "▶️",
        "completed": "✅",
        "failed": "❌"
    }.get(status, "❓")

    try:
        if isinstance(date, str):
            date = parser.isoparse(date)
        elif isinstance(date, int):
            date = datetime.fromtimestamp(date)
        formatted_date = escape_markdown(date.strftime('%d %B %Y, %H:%M'))
    except Exception as e:
        logging.error(f"Error processing date: {e}")
        formatted_date = "Unknown date"

    escaped_main_object = escape_markdown(str(main_object))
    escaped_uuid = escape_markdown(str(uuid))

    if tags:
        escaped_tags = ", ".join(f"[{escape_markdown(tag)}]" for tag in tags)
        tags_string = f"🏷️ {escaped_tags}"
    else:
        tags_string = ""

    result = (
        f"{verdict_icon} ***{formatted_date}***\n"
        f"📄 `{escaped_main_object}`\n"
        f"🆔 `{escaped_uuid}`\n"
    )

    if status in ['queued', 'running']:
        result += f"{status_icon} Status: {escape_markdown(status.capitalize())}\n"

    result += tags_string

    return result.strip()
