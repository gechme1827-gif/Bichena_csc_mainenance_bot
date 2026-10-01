import os
import json
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# SAME TELEGRAM ACCOUNT IS BOTH ADMIN AND TECHNICIAN
ADMIN_ID = 405014345
TECHNICIAN_IDS = [405014345]

DATA_FILE = "requests.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "requests": [],
            "users": {}
        }

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {
            "requests": [],
            "users": {}
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# ROLE CHECKS
# ============================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


def is_technician(user_id):
    return user_id in TECHNICIAN_IDS


# ============================================================
# USER MENU
# ============================================================

def user_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "📧 Generate Email",
                callback_data="generate"
            ),
            InlineKeyboardButton(
                "📋 My Emails",
                callback_data="my_emails"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔍 Check Email",
                callback_data="check"
            ),
            InlineKeyboardButton(
                "💰 My Credits",
                callback_data="credits"
            ),
        ],
        [
            InlineKeyboardButton(
                "👤 My Account",
                callback_data="account"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# ADMIN + TECHNICIAN MENU
# ============================================================

def admin_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 All Requests",
                callback_data="admin_requests"
            )
        ],
        [
            InlineKeyboardButton(
                "👨‍🔧 Technicians",
                callback_data="technicians"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 My Assigned Requests",
                callback_data="tech_requests"
            )
        ],
        [
            InlineKeyboardButton(
                "📧 Generate Email",
                callback_data="generate"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 My Emails",
                callback_data="my_emails"
            ),
            InlineKeyboardButton(
                "🔍 Check Email",
                callback_data="check"
            ),
        ],
        [
            InlineKeyboardButton(
                "👤 My Account",
                callback_data="account"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# FIND REQUEST
# ============================================================

def get_request(request_id):
    data = load_data()

    for request in data["requests"]:
        if request["id"] == request_id:
            return request

    return None


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    user_id = user.id

    data = load_data()

    data["users"][str(user_id)] = {
        "id": user_id,
        "name": user.full_name,
        "username": user.username,
    }

    save_data(data)

    # ADMIN + TECHNICIAN
    if is_admin(user_id) and is_technician(user_id):

        await update.message.reply_text(
            f"👋 Welcome {user.first_name}!\n\n"
            "👑 Role: ADMIN\n"
            "👨‍🔧 Role: TECHNICIAN\n\n"
            "You have both administrator and technician access.",
            reply_markup=admin_menu(),
        )

        return

    # ADMIN ONLY
    if is_admin(user_id):

        await update.message.reply_text(
            f"👑 Welcome Admin, {user.first_name}!\n\n"
            "You can manage requests and assign technicians.",
            reply_markup=admin_menu(),
        )

        return

    # TECHNICIAN ONLY
    if is_technician(user_id):

        await update.message.reply_text(
            f"👨‍🔧 Welcome Technician {user.first_name}!\n\n"
            "You can view requests assigned to you.",
            reply_markup=admin_menu(),
        )

        return

    # NORMAL USER
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        "Select an option:",
        reply_markup=user_menu(),
    )


# ============================================================
# GENERATE EMAIL / REQUEST
# ============================================================

async def generate_email(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    context.user_data["creating_request"] = True

    await query.message.reply_text(
        "📧 Generate Email Request\n\n"
        "Please send the request details.\n\n"
        "Example:\n\n"
        "Customer: ABC Company\n"
        "Service: New connection\n"
        "Power: 50 kW\n"
        "Location: Addis Ababa"
    )


# ============================================================
# RECEIVE NEW REQUEST
# ============================================================

async def receive_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("creating_request"):
        return

    user = update.effective_user
    message_text = update.message.text

    data = load_data()

    if data["requests"]:
        next_id = max(
            request["id"]
            for request in data["requests"]
        ) + 1
    else:
        next_id = 1

    request = {
        "id": next_id,
        "user_id": user.id,
        "user_name": user.full_name,
        "username": user.username,
        "details": message_text,
        "status": "Pending",
        "technician_id": None,
        "technician_name": None,
        "created_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }

    data["requests"].append(request)
    save_data(data)

    context.user_data["creating_request"] = False

    await update.message.reply_text(
        f"✅ Request submitted successfully!\n\n"
        f"🆔 Request ID: #{next_id}\n"
        f"📌 Status: Pending\n\n"
        "An administrator will review your request."
    )

    # SEND REQUEST TO ADMIN
    try:

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "📥 NEW REQUEST\n\n"
                f"🆔 Request ID: #{next_id}\n"
                f"👤 Customer: {user.full_name}\n"
                f"🆔 User ID: {user.id}\n\n"
                f"📝 Details:\n{message_text}"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "👨‍🔧 Assign Technician",
                            callback_data=f"assign_{next_id}"
                        )
                    ]
                ]
            ),
        )

    except Exception as error:
        logger.error(
            f"Could not notify admin: {error}"
        )


# ============================================================
# MY EMAILS
# ============================================================

async def my_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    data = load_data()

    requests = [
        request
        for request in data["requests"]
        if request["user_id"] == user_id
    ]

    if not requests:

        await query.message.reply_text(
            "📋 You don't have any requests yet."
        )

        return

    text = "📋 YOUR REQUESTS\n\n"

    for request in requests:

        technician = (
            request["technician_name"]
            or "Not assigned"
        )

        text += (
            f"🆔 #{request['id']}\n"
            f"📌 Status: {request['status']}\n"
            f"👨‍🔧 Technician: {technician}\n"
            f"📅 {request['created_at']}\n\n"
        )

    await query.message.reply_text(text)


# ============================================================
# CHECK REQUEST
# ============================================================

async def check_email(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    context.user_data["checking_request"] = True

    await query.message.reply_text(
        "🔍 Enter your Request ID.\n\n"
        "Example:\n"
        "15"
    )


# ============================================================
# RECEIVE CHECK REQUEST ID
# ============================================================

async def receive_check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("checking_request"):
        return

    try:
        request_id = int(
            update.message.text.strip()
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Please enter a valid Request ID."
        )

        return

    request = get_request(request_id)

    context.user_data["checking_request"] = False

    if not request:

        await update.message.reply_text(
            "❌ Request not found."
        )

        return

    user_id = update.effective_user.id

    if (
        request["user_id"] != user_id
        and not is_admin(user_id)
        and not is_technician(user_id)
    ):

        await update.message.reply_text(
            "❌ You are not authorized to view this request."
        )

        return

    await update.message.reply_text(
        f"🔍 REQUEST #{request['id']}\n\n"
        f"👤 Customer: {request['user_name']}\n"
        f"📌 Status: {request['status']}\n"
        f"👨‍🔧 Technician: "
        f"{request['technician_name'] or 'Not assigned'}\n"
        f"📅 Created: {request['created_at']}\n\n"
        f"📝 Details:\n{request['details']}"
    )


# ============================================================
# CREDITS
# ============================================================

async def credits(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "💰 MY CREDITS\n\n"
        "Credits: 0\n\n"
        "Credit management can be added later."
    )


# ============================================================
# ACCOUNT
# ============================================================

async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    roles = []

    if is_admin(user.id):
        roles.append("👑 Administrator")

    if is_technician(user.id):
        roles.append("👨‍🔧 Technician")

    if not roles:
        roles.append("👤 User")

    await query.message.reply_text(
        f"👤 MY ACCOUNT\n\n"
        f"Name: {user.full_name}\n"
        f"Username: "
        f"@{user.username if user.username else 'None'}\n"
        f"Telegram ID: {user.id}\n\n"
        "Roles:\n"
        + "\n".join(roles)
    )


# ============================================================
# ADMIN - ALL REQUESTS
# ============================================================

async def admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = load_data()

    if not data["requests"]:

        await query.message.reply_text(
            "📋 No requests available."
        )

        return

    for request in data["requests"]:

        technician = (
            request["technician_name"]
            or "Not assigned"
        )

        keyboard = []

        if not request["technician_id"]:

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "👨‍🔧 Assign Technician",
                        callback_data=f"assign_{request['id']}"
                    )
                ]
            )

        await query.message.reply_text(
            f"🆔 REQUEST #{request['id']}\n\n"
            f"👤 Customer: {request['user_name']}\n"
            f"📌 Status: {request['status']}\n"
            f"👨‍🔧 Technician: {technician}\n"
            f"📅 Created: {request['created_at']}\n\n"
            f"📝 Details:\n{request['details']}",
            reply_markup=(
                InlineKeyboardMarkup(keyboard)
                if keyboard
                else None
            )
        )


# ============================================================
# ASSIGN TECHNICIAN
# ============================================================

async def assign_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    request_id = int(
        query.data.split("_")[1]
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "👨‍🔧 Assign to Me",
                callback_data=f"tech_{request_id}_{ADMIN_ID}"
            )
        ]
    ]

    await query.message.reply_text(
        f"👨‍🔧 Select technician for Request #{request_id}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# TECHNICIANS
# ============================================================

async def technicians(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    await query.message.reply_text(
        "👨‍🔧 TECHNICIANS\n\n"
        "1. Admin / Technician\n"
        "Telegram ID: 405014345\n"
        "Status: Active"
    )


# ============================================================
# ASSIGN TECHNICIAN
# ============================================================

async def technician_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    parts = query.data.split("_")

    request_id = int(parts[1])
    technician_id = int(parts[2])

    data = load_data()

    request = None

    for item in data["requests"]:

        if item["id"] == request_id:
            request = item
            break

    if not request:

        await query.message.reply_text(
            "❌ Request not found."
        )

        return

    technician_name = "Admin / Technician"

    request["technician_id"] = technician_id
    request["technician_name"] = technician_name
    request["status"] = "Assigned"

    save_data(data)

    await query.message.reply_text(
        f"✅ Request #{request_id} assigned successfully.\n\n"
        f"👨‍🔧 Technician: {technician_name}\n"
        f"🆔 Technician ID: {technician_id}\n"
        f"📌 Status: Assigned"
    )

    # NOTIFY TECHNICIAN
    try:

        await context.bot.send_message(
            chat_id=technician_id,
            text=(
                "📥 NEW ASSIGNED REQUEST\n\n"
                f"🆔 Request #{request_id}\n"
                f"👤 Customer: {request['user_name']}\n\n"
                f"📝 Details:\n{request['details']}\n\n"
                "📌 Status: Assigned"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "▶️ Start",
                            callback_data=f"startwork_{request_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ Reject",
                            callback_data=f"reject_{request_id}"
                        )
                    ],
                ]
            )
        )

    except Exception as error:

        logger.error(
            f"Could not notify technician: {error}"
        )


# ============================================================
# TECHNICIAN REQUESTS
# ============================================================

async def tech_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    technician_id = query.from_user.id

    if not is_technician(technician_id):
        return

    data = load_data()

    requests = [
        request
        for request in data["requests"]
        if request["technician_id"] == technician_id
    ]

    if not requests:

        await query.message.reply_text(
            "📋 You don't have any assigned requests."
        )

        return

    for request in requests:

        keyboard = []

        if request["status"] == "Assigned":

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "▶️ Start",
                        callback_data=f"startwork_{request['id']}"
                    )
                ]
            )

        elif request["status"] == "In Progress":

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "✅ Complete",
                        callback_data=f"complete_{request['id']}"
                    )
                ]
            )

        await query.message.reply_text(
            f"🆔 REQUEST #{request['id']}\n\n"
            f"👤 Customer: {request['user_name']}\n"
            f"📌 Status: {request['status']}\n\n"
            f"📝 Details:\n{request['details']}",
            reply_markup=(
                InlineKeyboardMarkup(keyboard)
                if keyboard
                else None
            )
        )


# ============================================================
# START WORK
# ============================================================

async def start_work(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    technician_id = query.from_user.id

    request_id = int(
        query.data.split("_")[1]
    )

    data = load_data()

    request = None

    for item in data["requests"]:

        if item["id"] == request_id:
            request = item
            break

    if not request:
        return

    if request["technician_id"] != technician_id:

        await query.message.reply_text(
            "❌ This request is not assigned to you."
        )

        return

    request["status"] = "In Progress"

    save_data(data)

    await query.message.reply_text(
        f"▶️ Request #{request_id}\n\n"
        "📌 Status: IN PROGRESS"
    )

    # NOTIFY CUSTOMER
    try:

        await context.bot.send_message(
            chat_id=request["user_id"],
            text=(
                f"🔄 Request #{request_id} Update\n\n"
                "A technician has started working on your request.\n\n"
                "📌 Status: In Progress"
            )
        )

    except Exception as error:

        logger.error(
            f"Could not notify customer: {error}"
        )


# ============================================================
# COMPLETE REQUEST
# ============================================================

async def complete_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    technician_id = query.from_user.id

    request_id = int(
        query.data.split("_")[1]
    )

    data = load_data()

    request = None

    for item in data["requests"]:

        if item["id"] == request_id:
            request = item
            break

    if not request:
        return

    if request["technician_id"] != technician_id:

        await query.message.reply_text(
            "❌ This request is not assigned to you."
        )

        return

    request["status"] = "Completed"

    save_data(data)

    await query.message.reply_text(
        f"✅ Request #{request_id}\n\n"
        "📌 Status: COMPLETED"
    )

    # NOTIFY CUSTOMER
    try:

        await context.bot.send_message(
            chat_id=request["user_id"],
            text=(
                f"✅ Request #{request_id} Completed\n\n"
                "Your request has been completed by the technician."
            )
        )

    except Exception as error:

        logger.error(
            f"Could not notify customer: {error}"
        )


# ============================================================
# REJECT REQUEST
# ============================================================

async def reject_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    technician_id = query.from_user.id

    request_id = int(
        query.data.split("_")[1]
    )

    data = load_data()

    request = None

    for item in data["requests"]:

        if item["id"] == request_id:
            request = item
            break

    if not request:
        return

    if request["technician_id"] != technician_id:

        await query.message.reply_text(
            "❌ This request is not assigned to you."
        )

        return

    request["status"] = "Rejected"

    save_data(data)

    await query.message.reply_text(
        f"❌ Request #{request_id} rejected."
    )

    # NOTIFY ADMIN
    try:

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "⚠️ REQUEST REJECTED\n\n"
                f"Request #{request_id}\n"
                "Technician: Admin / Technician\n\n"
                "Please review the request."
            )
        )

    except Exception as error:

        logger.error(
            f"Could not notify admin: {error}"
        )


# ============================================================
# BUTTON ROUTER
# ============================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    action = query.data

    if action == "generate":
        await generate_email(update, context)

    elif action == "my_emails":
        await my_emails(update, context)

    elif action == "check":
        await check_email(update, context)

    elif action == "credits":
        await credits(update, context)

    elif action == "account":
        await account(update, context)

    elif action == "admin_requests":
        await admin_requests(update, context)

    elif action == "technicians":
        await technicians(update, context)

    elif action == "tech_requests":
        await tech_requests(update, context)

    elif action.startswith("assign_"):
        await assign_request(update, context)

    elif action.startswith("tech_"):
        await technician_selected(update, context)

    elif action.startswith("startwork_"):
        await start_work(update, context)

    elif action.startswith("complete_"):
        await complete_request(update, context)

    elif action.startswith("reject_"):
        await reject_request(update, context)


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN environment variable is missing."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_request
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_check
        )
    )

    logger.info("Telegram bot started.")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
