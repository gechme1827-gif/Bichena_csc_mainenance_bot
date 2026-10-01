import os
import sqlite3
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")

# Add Telegram numeric user IDs of your authorized administrators.
# Example:
# ADMIN_IDS = {123456789, 987654321}
ADMIN_IDS = {405014345})

DB_FILE = "maintenance_bot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# ============================================================
# CONVERSATION STATES
# ============================================================

(
    METER_NUMBER,
    PHONE,
    PROBLEM_TYPE,
    PROBLEM_DETAILS,
    LOCATION,
    PHOTO,
    CONFIRM,
) = range(7)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            phone TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_no TEXT UNIQUE,
            telegram_id INTEGER NOT NULL,
            meter_number TEXT,
            phone TEXT,
            problem_type TEXT,
            problem_details TEXT,
            location TEXT,
            latitude REAL,
            longitude REAL,
            photo_file_id TEXT,
            status TEXT DEFAULT 'NEW',
            priority TEXT DEFAULT 'NORMAL',
            technician TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_user(user):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users
        (telegram_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.now().isoformat(timespec="seconds"),
    ))

    conn.commit()
    conn.close()


def create_request(data):
    conn = get_db()
    cur = conn.cursor()

    now = datetime.now().isoformat(timespec="seconds")

    cur.execute("""
        INSERT INTO requests (
            request_no,
            telegram_id,
            meter_number,
            phone,
            problem_type,
            problem_details,
            location,
            latitude,
            longitude,
            photo_file_id,
            status,
            priority,
            technician,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "TEMP",
        data["telegram_id"],
        data["meter_number"],
        data["phone"],
        data["problem_type"],
        data["problem_details"],
        data["location"],
        data.get("latitude"),
        data.get("longitude"),
        data.get("photo_file_id"),
        "NEW",
        data.get("priority", "NORMAL"),
        "",
        now,
        now,
    ))

    request_id = cur.lastrowid
    request_no = f"MR-{request_id:04d}"

    cur.execute("""
        UPDATE requests
        SET request_no = ?
        WHERE id = ?
    """, (request_no, request_id))

    conn.commit()
    conn.close()

    return request_no


def get_request(request_no):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM requests WHERE request_no = ?",
        (request_no.upper(),),
    )

    result = cur.fetchone()

    conn.close()

    return result


def get_user_requests(telegram_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM requests
        WHERE telegram_id = ?
        ORDER BY id DESC
    """, (telegram_id,))

    results = cur.fetchall()

    conn.close()

    return results


def get_new_requests():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM requests
        WHERE status = 'NEW'
        ORDER BY id ASC
    """)

    results = cur.fetchall()

    conn.close()

    return results


def update_request_status(request_no, status):
    conn = get_db()

    conn.execute("""
        UPDATE requests
        SET status = ?, updated_at = ?
        WHERE request_no = ?
    """, (
        status,
        datetime.now().isoformat(timespec="seconds"),
        request_no.upper(),
    ))

    conn.commit()
    conn.close()


def assign_technician(request_no, technician):
    conn = get_db()

    conn.execute("""
        UPDATE requests
        SET technician = ?, updated_at = ?
        WHERE request_no = ?
    """, (
        technician,
        datetime.now().isoformat(timespec="seconds"),
        request_no.upper(),
    ))

    conn.commit()
    conn.close()


# ============================================================
# KEYBOARDS
# ============================================================

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "🔧 Submit Maintenance Request",
                callback_data="submit",
            )
        ],
        [
            InlineKeyboardButton(
                "🔎 Track Request",
                callback_data="track",
            ),
            InlineKeyboardButton(
                "📋 My Requests",
                callback_data="my_requests",
            ),
        ],
        [
            InlineKeyboardButton(
                "👤 My Information",
                callback_data="my_info",
            ),
            InlineKeyboardButton(
                "📞 Help",
                callback_data="help",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def admin_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "📥 New Requests",
                callback_data="admin_new",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Request Statistics",
                callback_data="admin_stats",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    save_user(user)

    text = (
        "⚡ *Electric Utility Customer Service Bot*\n\n"
        "Welcome, {}!\n\n"
        "You can use this bot to submit and track "
        "maintenance requests.\n\n"
        "Please select an option:"
    ).format(user.first_name or "Customer")

    keyboard = main_menu()

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )


# ============================================================
# SUBMIT REQUEST
# ============================================================

async def submit_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    context.user_data["telegram_id"] = update.effective_user.id

    await query.edit_message_text(
        "🔧 *New Maintenance Request*\n\n"
        "Step 1 of 6\n\n"
        "Please enter your *meter/customer number*:",
        parse_mode="Markdown",
    )

    return METER_NUMBER


async def receive_meter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["meter_number"] = update.message.text.strip()

    await update.message.reply_text(
        "Step 2 of 6\n\n"
        "Please enter your phone number:"
    )

    return PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text.strip()

    keyboard = [
        [
            InlineKeyboardButton(
                "⚡ No Power",
                callback_data="problem_no_power",
            )
        ],
        [
            InlineKeyboardButton(
                "💡 Low Voltage",
                callback_data="problem_low_voltage",
            )
        ],
        [
            InlineKeyboardButton(
                "🔥 Meter Problem",
                callback_data="problem_meter",
            )
        ],
        [
            InlineKeyboardButton(
                "🔌 Line / Cable Problem",
                callback_data="problem_line",
            )
        ],
        [
            InlineKeyboardButton(
                "⚠️ Other",
                callback_data="problem_other",
            )
        ],
    ]

    await update.message.reply_text(
        "Step 3 of 6\n\n"
        "Select the type of problem:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return PROBLEM_TYPE


async def receive_problem_type(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    problem_types = {
        "problem_no_power": "No Power",
        "problem_low_voltage": "Low Voltage",
        "problem_meter": "Meter Problem",
        "problem_line": "Line / Cable Problem",
        "problem_other": "Other",
    }

    context.user_data["problem_type"] = problem_types.get(
        query.data,
        "Other",
    )

    await query.edit_message_text(
        "Step 4 of 6\n\n"
        "Please describe the problem in detail.\n\n"
        "Example:\n"
        "Power has been interrupted since morning.",
    )

    return PROBLEM_DETAILS


async def receive_problem_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["problem_details"] = update.message.text.strip()

    keyboard = [
        [
            InlineKeyboardButton(
                "📍 Share My Location",
                callback_data="share_location",
            )
        ],
        [
            InlineKeyboardButton(
                "✍️ Enter Address Manually",
                callback_data="manual_location",
            )
        ],
    ]

    await update.message.reply_text(
        "Step 5 of 6\n\n"
        "Please provide the location of the problem.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return LOCATION


async def request_location(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if query.data == "share_location":
        keyboard = [
            [
                InlineKeyboardButton(
                    "📍 Send Location",
                    callback_data="location_instruction",
                )
            ]
        ]

        await query.edit_message_text(
            "Please use Telegram's 📎 attachment button and "
            "select *Location* to send your current location.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    else:
        await query.edit_message_text(
            "Please type the full address/location of the problem."
        )

    return LOCATION


async def receive_location(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.message.location:
        location = update.message.location

        context.user_data["location"] = (
            f"GPS: {location.latitude}, {location.longitude}"
        )

        context.user_data["latitude"] = location.latitude
        context.user_data["longitude"] = location.longitude

        await update.message.reply_text(
            "Location received successfully."
        )

        await ask_for_photo(update, context)

        return PHOTO

    context.user_data["location"] = update.message.text.strip()

    await ask_for_photo(update, context)

    return PHOTO


async def ask_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "📷 Skip Photo",
                callback_data="skip_photo",
            )
        ]
    ]

    await update.message.reply_text(
        "Step 6 of 6\n\n"
        "You can now send a photo of the problem.\n\n"
        "If you don't have a photo, tap *Skip Photo*.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def receive_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.message.photo:
        photo = update.message.photo[-1]

        context.user_data["photo_file_id"] = photo.file_id

        await show_confirmation(update, context)

        return CONFIRM

    await show_confirmation(update, context)

    return CONFIRM


async def skip_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    context.user_data["photo_file_id"] = None

    await query.edit_message_text(
        "No photo attached."
    )

    fake_update = None

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Submit Request",
                callback_data="confirm_request",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_request",
            )
        ],
    ]

    data = context.user_data

    text = (
        "📋 *Confirm Maintenance Request*\n\n"
        f"Meter: `{data.get('meter_number')}`\n"
        f"Phone: `{data.get('phone')}`\n"
        f"Problem: {data.get('problem_type')}\n"
        f"Details: {data.get('problem_details')}\n"
        f"Location: {data.get('location')}\n"
        f"Photo: {'Yes' if data.get('photo_file_id') else 'No'}\n\n"
        "Submit this request?"
    )

    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    return CONFIRM


async def show_confirmation(update, context):
    data = context.user_data

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Submit Request",
                callback_data="confirm_request",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_request",
            )
        ],
    ]

    text = (
        "📋 *Confirm Maintenance Request*\n\n"
        f"Meter: `{data.get('meter_number')}`\n"
        f"Phone: `{data.get('phone')}`\n"
        f"Problem: {data.get('problem_type')}\n"
        f"Details: {data.get('problem_details')}\n"
        f"Location: {data.get('location')}\n"
        f"Photo: {'Yes' if data.get('photo_file_id') else 'No'}\n\n"
        "Submit this request?"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ============================================================
# CONFIRM REQUEST
# ============================================================

async def confirm_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    data = context.user_data

    request_no = create_request(data)

    await query.edit_message_text(
        "✅ *Request submitted successfully!*\n\n"
        f"Your request number is:\n"
        f"*{request_no}*\n\n"
        "Please keep this number so you can track your request.\n\n"
        "Status: *NEW*",
        parse_mode="Markdown",
    )

    # Notify administrators
    admin_text = (
        "🚨 *NEW MAINTENANCE REQUEST*\n\n"
        f"Request: *{request_no}*\n"
        f"Meter: `{data.get('meter_number')}`\n"
        f"Phone: `{data.get('phone')}`\n"
        f"Problem: {data.get('problem_type')}\n"
        f"Details: {data.get('problem_details')}\n"
        f"Location: {data.get('location')}\n"
        f"Customer Telegram ID: `{data.get('telegram_id')}`"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="Markdown",
            )

            if data.get("photo_file_id"):
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=data["photo_file_id"],
                    caption=f"Photo - {request_no}",
                )

        except Exception as e:
            logger.error(
                "Could not notify admin %s: %s",
                admin_id,
                e,
            )

    context.user_data.clear()

    return ConversationHandler.END


async def cancel_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "❌ Request cancelled.\n\n"
        "Use /start to return to the main menu."
    )

    return ConversationHandler.END


async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Operation cancelled.\n\n"
        "Use /start to return to the main menu."
    )

    return ConversationHandler.END


# ============================================================
# TRACK REQUEST
# ============================================================

async def track_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["tracking"] = True

    await query.edit_message_text(
        "🔎 *Track Request*\n\n"
        "Enter your request number.\n\n"
        "Example: `MR-0001`",
        parse_mode="Markdown",
    )

    return


async def process_tracking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    request_no = update.message.text.strip().upper()

    request = get_request(request_no)

    if not request:
        await update.message.reply_text(
            "❌ Request not found.\n\n"
            "Please check the request number and try again."
        )
        return

    status = request["status"]
    technician = request["technician"] or "Not assigned"

    text = (
        "🔎 *Request Information*\n\n"
        f"Request: *{request['request_no']}*\n"
        f"Problem: {request['problem_type']}\n"
        f"Status: *{status}*\n"
        f"Technician: {technician}\n"
        f"Created: {request['created_at']}"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

    context.user_data.pop("tracking", None)


# ============================================================
# MY REQUESTS
# ============================================================

async def my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_user.id

    requests = get_user_requests(telegram_id)

    if not requests:
        await query.edit_message_text(
            "📋 You don't have any maintenance requests yet.",
            reply_markup=main_menu(),
        )
        return

    text = "📋 *My Maintenance Requests*\n\n"

    for req in requests[:15]:
        text += (
            f"🔹 *{req['request_no']}*\n"
            f"Problem: {req['problem_type']}\n"
            f"Status: *{req['status']}*\n"
            f"Date: {req['created_at']}\n\n"
        )

    await query.edit_message_text(
        text,
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# USER INFORMATION
# ============================================================

async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    requests = get_user_requests(user.id)

    text = (
        "👤 *My Information*\n\n"
        f"Name: {user.first_name or '-'}\n"
        f"Username: @{user.username if user.username else '-'}\n"
        f"Telegram ID: `{user.id}`\n"
        f"Total Requests: {len(requests)}"
    )

    await query.edit_message_text(
        text,
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# HELP
# ============================================================

async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "📞 *Help*\n\n"
        "Use this bot to report electricity maintenance problems.\n\n"
        "For emergencies involving electrical hazards, "
        "stay away from damaged equipment and contact "
        "the appropriate utility emergency service.\n\n"
        "To return to the main menu, use /start."
    )

    await query.edit_message_text(
        text,
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# ADMIN CHECK
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "⛔ You are not authorized to access the admin panel."
        )
        return

    await update.message.reply_text(
        "👨‍💼 *Admin Panel*",
        reply_markup=admin_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# ADMIN NEW REQUESTS
# ============================================================

async def admin_new_requests(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "⛔ Unauthorized."
        )
        return

    requests = get_new_requests()

    if not requests:
        await query.edit_message_text(
            "📥 There are no new requests.",
            reply_markup=admin_menu(),
        )
        return

    text = "📥 *NEW REQUESTS*\n\n"

    keyboard = []

    for req in requests[:20]:
        text += (
            f"*{req['request_no']}* — "
            f"{req['problem_type']}\n"
            f"Meter: {req['meter_number']}\n"
            f"Phone: {req['phone']}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"🔎 {req['request_no']}",
                callback_data=f"view_{req['request_no']}",
            )
        ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ============================================================
# ADMIN VIEW REQUEST
# ============================================================

async def admin_view_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "⛔ Unauthorized."
        )
        return

    request_no = query.data.replace("view_", "", 1)

    request = get_request(request_no)

    if not request:
        await query.edit_message_text(
            "Request not found."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 In Progress",
                callback_data=f"status_{request_no}_IN_PROGRESS",
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Completed",
                callback_data=f"status_{request_no}_COMPLETED",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Rejected",
                callback_data=f"status_{request_no}_REJECTED",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="admin_new",
            )
        ],
    ]

    text = (
        f"🔎 *Request {request['request_no']}*\n\n"
        f"Meter: `{request['meter_number']}`\n"
        f"Phone: `{request['phone']}`\n"
        f"Problem: {request['problem_type']}\n"
        f"Details: {request['problem_details']}\n"
        f"Location: {request['location']}\n"
        f"Status: *{request['status']}*\n"
        f"Technician: {request['technician'] or 'Not assigned'}\n"
        f"Created: {request['created_at']}"
    )

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

    if request["photo_file_id"]:
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=request["photo_file_id"],
                caption=f"Photo - {request['request_no']}",
            )
        except Exception as e:
            logger.error("Photo sending error: %s", e)


# ============================================================
# ADMIN STATUS UPDATE
# ============================================================

async def admin_status_update(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "⛔ Unauthorized."
        )
        return

    parts = query.data.split("_", 2)

    request_no = parts[1]
    status = parts[2]

    update_request_status(request_no, status)

    request = get_request(request_no)

    if request:
        customer_id = request["telegram_id"]

        customer_text = (
            f"🔔 *Maintenance Request Update*\n\n"
            f"Request: *{request_no}*\n"
            f"New Status: *{status}*"
        )

        try:
            await context.bot.send_message(
                chat_id=customer_id,
                text=customer_text,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(
                "Could not notify customer: %s",
                e,
            )

    await query.edit_message_text(
        f"✅ Request *{request_no}* updated.\n\n"
        f"New status: *{status}*",
        reply_markup=admin_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# ADMIN STATISTICS
# ============================================================

async def admin_statistics(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            "⛔ Unauthorized."
        )
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM requests")
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM requests WHERE status = 'NEW'"
    )
    new = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM requests WHERE status = 'IN_PROGRESS'"
    )
    in_progress = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM requests WHERE status = 'COMPLETED'"
    )
    completed = cur.fetchone()[0]

    conn.close()

    text = (
        "📊 *Request Statistics*\n\n"
        f"Total: {total}\n"
        f"New: {new}\n"
        f"In Progress: {in_progress}\n"
        f"Completed: {completed}"
    )

    await query.edit_message_text(
        text,
        reply_markup=admin_menu(),
        parse_mode="Markdown",
    )


# ============================================================
# GENERAL MESSAGE ROUTER
# ============================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if context.user_data.get("tracking"):
        await process_tracking(update, context)
        return

    await update.message.reply_text(
        "Please use the menu below:",
        reply_markup=main_menu(),
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update, context):
    logger.error(
        "Exception while handling update:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set."
        )

    init_db()

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # Maintenance request conversation
    # --------------------------------------------------------

    request_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                submit_request,
                pattern="^submit$",
            )
        ],
        states={
            METER_NUMBER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_meter,
                )
            ],

            PHONE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_phone,
                )
            ],

            PROBLEM_TYPE: [
                CallbackQueryHandler(
                    receive_problem_type,
                    pattern="^problem_",
                )
            ],

            PROBLEM_DETAILS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_problem_details,
                )
            ],

            LOCATION: [
                CallbackQueryHandler(
                    request_location,
                    pattern="^(share_location|manual_location)$",
                ),
                MessageHandler(
                    filters.LOCATION,
                    receive_location,
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_location,
                ),
            ],

            PHOTO: [
                CallbackQueryHandler(
                    skip_photo,
                    pattern="^skip_photo$",
                ),
                MessageHandler(
                    filters.PHOTO,
                    receive_photo,
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_photo,
                ),
            ],

            CONFIRM: [
                CallbackQueryHandler(
                    confirm_request,
                    pattern="^confirm_request$",
                ),
                CallbackQueryHandler(
                    cancel_request,
                    pattern="^cancel_request$",
                ),
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel_command,
            )
        ],
    )

    application.add_handler(request_conversation)

    # --------------------------------------------------------
    # Main menu callbacks
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            track_request,
            pattern="^track$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            my_requests,
            pattern="^my_requests$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            my_info,
            pattern="^my_info$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            help_menu,
            pattern="^help$",
        )
    )

    # --------------------------------------------------------
    # Admin callbacks
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            admin_new_requests,
            pattern="^admin_new$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_statistics,
            pattern="^admin_stats$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_view_request,
            pattern="^view_",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_status_update,
            pattern="^status_",
        )
    )

    # --------------------------------------------------------
    # Commands
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("admin", admin_command)
    )

    application.add_handler(
        CommandHandler("cancel", cancel_command)
    )

    # --------------------------------------------------------
    # Location handler
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.LOCATION,
            receive_location,
        )
    )

    # --------------------------------------------------------
    # General messages
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text,
        )
    )

    application.add_error_handler(error_handler)

    print("Bot started successfully...")

    application.run_polling()


if __name__ == "__main__":
    main()
