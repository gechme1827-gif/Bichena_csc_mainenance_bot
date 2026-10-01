import os
import json
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
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Your Telegram ID
ADMIN_ID = 405014345

# The same person is both Admin and Technician
TECHNICIAN_IDS = [405014345]

CUSTOMERS_FILE = "customers.json"
REQUESTS_FILE = "requests.json"


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def load_json(filename, default):
    try:
        if not os.path.exists(filename):
            return default

        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def load_customers():
    return load_json(CUSTOMERS_FILE, {})


def save_customers(data):
    save_json(CUSTOMERS_FILE, data)


def load_requests():
    return load_json(REQUESTS_FILE, [])


def save_requests(data):
    save_json(REQUESTS_FILE, data)


# =========================================================
# ROLE CHECKS
# =========================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


def is_technician(user_id):
    return user_id in TECHNICIAN_IDS


# =========================================================
# CUSTOMER REGISTRATION
# =========================================================

def customer_registered(user_id):
    customers = load_customers()
    return str(user_id) in customers


async def start_registration(update, context):
    context.user_data.clear()

    context.user_data["registering"] = True
    context.user_data["registration_step"] = "full_name"

    await update.message.reply_text(
        "📝 Customer Registration\n\n"
        "Please enter your **full name**:",
        parse_mode="Markdown"
    )


async def process_registration(update, context):

    text = update.message.text.strip()
    step = context.user_data.get("registration_step")

    if step == "full_name":

        context.user_data["reg_full_name"] = text
        context.user_data["registration_step"] = "phone"

        await update.message.reply_text(
            "📱 Please enter your **phone number**:"
        )
        return

    if step == "phone":

        context.user_data["reg_phone"] = text
        context.user_data["registration_step"] = "customer_number"

        await update.message.reply_text(
            "🆔 Please enter your **Customer / Account Number**:"
        )
        return

    if step == "customer_number":

        context.user_data["reg_customer_number"] = text
        context.user_data["registration_step"] = "address"

        await update.message.reply_text(
            "📍 Please enter your **full address/location**:"
        )
        return

    if step == "address":

        context.user_data["reg_address"] = text
        context.user_data["registration_step"] = "organization"

        await update.message.reply_text(
            "🏢 Please enter your **company/organization name**.\n\n"
            "If you are an individual customer, type: Individual"
        )
        return

    if step == "organization":

        context.user_data["reg_organization"] = text
        context.user_data["registration_step"] = "email"

        await update.message.reply_text(
            "📧 Please enter your **email address**:"
        )
        return

    if step == "email":

        context.user_data["reg_email"] = text

        user = update.effective_user

        customers = load_customers()

        customers[str(user.id)] = {
            "telegram_id": user.id,
            "telegram_username": user.username or "",
            "full_name": context.user_data["reg_full_name"],
            "phone": context.user_data["reg_phone"],
            "customer_number": context.user_data["reg_customer_number"],
            "address": context.user_data["reg_address"],
            "organization": context.user_data["reg_organization"],
            "email": context.user_data["reg_email"],
            "registered_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

        save_customers(customers)

        context.user_data.pop("registering", None)
        context.user_data.pop("registration_step", None)

        await update.message.reply_text(
            "✅ **Registration completed successfully!**\n\n"
            "You can now submit a request.",
            parse_mode="Markdown"
        )

        await show_main_menu(update, context)


# =========================================================
# MENUS
# =========================================================

def customer_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📨 Request",
                callback_data="request"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 My Requests",
                callback_data="my_requests"
            )
        ],
        [
            InlineKeyboardButton(
                "🔍 Check Request",
                callback_data="check_request"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 My Credits",
                callback_data="credits"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 My Account",
                callback_data="account"
            )
        ]
    ])


def admin_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📋 All Requests",
                callback_data="all_requests"
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
                callback_data="technician_requests"
            )
        ],
        [
            InlineKeyboardButton(
                "📨 Request",
                callback_data="request"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 My Requests",
                callback_data="my_requests"
            )
        ],
        [
            InlineKeyboardButton(
                "🔍 Check Request",
                callback_data="check_request"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 My Account",
                callback_data="account"
            )
        ]
    ])


async def show_main_menu(update, context):

    user = update.effective_user

    if is_admin(user.id) or is_technician(user.id):

        await update.message.reply_text(
            "🏠 **Main Menu**\n\n"
            "Role: 👑 Admin + 👨‍🔧 Technician",
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )

    else:

        await update.message.reply_text(
            "🏠 **Customer Menu**\n\n"
            "Select an option:",
            reply_markup=customer_menu(),
            parse_mode="Markdown"
        )


# =========================================================
# START COMMAND
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    customers = load_customers()

    # Automatically store basic Telegram information
    if str(user.id) not in customers:

        customers[str(user.id)] = {
            "telegram_id": user.id,
            "telegram_username": user.username or "",
            "full_name": "",
            "phone": "",
            "customer_number": "",
            "address": "",
            "organization": "",
            "email": "",
            "registered_at": ""
        }

        save_customers(customers)

    if not customer_registered(user.id):

        await update.message.reply_text(
            "👋 Welcome!\n\n"
            "You must complete your customer registration "
            "before submitting a request."
        )

        await start_registration(update, context)
        return

    await show_main_menu(update, context)


# =========================================================
# REQUEST CREATION
# =========================================================

async def start_request(update, context):

    user = update.effective_user

    if not customer_registered(user.id):

        await update.callback_query.answer()

        await update.callback_query.message.reply_text(
            "⚠️ You must register first."
        )

        context.user_data.clear()
        context.user_data["registering"] = True
        context.user_data["registration_step"] = "full_name"

        await update.callback_query.message.reply_text(
            "📝 Please enter your **full name**:",
            parse_mode="Markdown"
        )

        return

    context.user_data["creating_request"] = True

    await update.callback_query.answer()

    await update.callback_query.message.reply_text(
        "📨 **New Request**\n\n"
        "Please describe your request in detail.\n\n"
        "Include important information such as:\n"
        "• Service required\n"
        "• Problem description\n"
        "• Location\n"
        "• Any other useful information",
        parse_mode="Markdown"
    )


async def receive_request(update, context):

    user = update.effective_user

    details = update.message.text.strip()

    customers = load_customers()

    customer = customers.get(str(user.id))

    if not customer:
        await update.message.reply_text(
            "⚠️ Customer registration not found.\n"
            "Please use /start."
        )
        return

    requests = load_requests()

    if requests:
        request_id = max(
            int(r["id"]) for r in requests
        ) + 1
    else:
        request_id = 1

    request = {
        "id": request_id,
        "user_id": user.id,
        "user_name": customer["full_name"],
        "username": customer["telegram_username"],
        "phone": customer["phone"],
        "customer_number": customer["customer_number"],
        "address": customer["address"],
        "organization": customer["organization"],
        "email": customer["email"],
        "details": details,
        "status": "Pending",
        "technician_id": None,
        "technician_name": "",
        "created_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    requests.append(request)

    save_requests(requests)

    context.user_data.pop("creating_request", None)

    await update.message.reply_text(
        f"✅ **Request submitted successfully!**\n\n"
        f"📋 Request ID: **#{request_id}**\n"
        f"📌 Status: **Pending**\n\n"
        f"An administrator will assign a technician.",
        parse_mode="Markdown"
    )

    # Notify admin
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👨‍🔧 Assign Technician",
                callback_data=f"assign_{request_id}"
            )
        ]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📨 **New Customer Request**\n\n"
            f"📋 Request ID: #{request_id}\n\n"
            f"👤 Customer: {customer['full_name']}\n"
            f"📱 Phone: {customer['phone']}\n"
            f"🆔 Account: {customer['customer_number']}\n"
            f"🏢 Organization: {customer['organization']}\n"
            f"📍 Address: {customer['address']}\n"
            f"📧 Email: {customer['email']}\n\n"
            f"📝 Request:\n{details}\n\n"
            f"📌 Status: Pending"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# =========================================================
# MY REQUESTS
# =========================================================

async def my_requests(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    requests = load_requests()

    my_requests_list = [
        r for r in requests
        if r["user_id"] == user.id
    ]

    if not my_requests_list:

        await query.message.reply_text(
            "📋 You have no requests yet."
        )
        return

    text = "📋 **My Requests**\n\n"

    for r in my_requests_list:

        text += (
            f"📋 **#{r['id']}**\n"
            f"📌 Status: {r['status']}\n"
            f"👨‍🔧 Technician: "
            f"{r['technician_name'] or 'Not assigned'}\n"
            f"📅 {r['created_at']}\n\n"
        )

    await query.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# CHECK REQUEST
# =========================================================

async def start_check_request(update, context):

    query = update.callback_query

    await query.answer()

    context.user_data["checking_request"] = True

    await query.message.reply_text(
        "🔍 Enter the **Request ID** you want to check:",
        parse_mode="Markdown"
    )


async def receive_check(update, context):

    user = update.effective_user

    try:
        request_id = int(update.message.text.strip())
    except ValueError:

        await update.message.reply_text(
            "⚠️ Please enter a valid Request ID."
        )
        return

    requests = load_requests()

    request = next(
        (
            r for r in requests
            if int(r["id"]) == request_id
        ),
        None
    )

    if not request:

        await update.message.reply_text(
            "❌ Request not found."
        )

        context.user_data.pop("checking_request", None)
        return

    # Customer can only see own request
    # Admin/technician can see all requests
    if (
        request["user_id"] != user.id
        and not is_admin(user.id)
        and not is_technician(user.id)
    ):

        await update.message.reply_text(
            "⛔ You are not authorized to view this request."
        )

        context.user_data.pop("checking_request", None)
        return

    text = (
        f"📋 **Request #{request['id']}**\n\n"
        f"👤 Customer: {request['user_name']}\n"
        f"📱 Phone: {request['phone']}\n"
        f"🆔 Account: {request['customer_number']}\n"
        f"🏢 Organization: {request['organization']}\n"
        f"📍 Address: {request['address']}\n"
        f"📧 Email: {request['email']}\n\n"
        f"📝 Request:\n{request['details']}\n\n"
        f"📌 Status: {request['status']}\n"
        f"👨‍🔧 Technician: "
        f"{request['technician_name'] or 'Not assigned'}\n"
        f"📅 Created: {request['created_at']}"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )

    context.user_data.pop("checking_request", None)


# =========================================================
# ADMIN - ALL REQUESTS
# =========================================================

async def all_requests(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    if not is_admin(user.id):

        await query.message.reply_text(
            "⛔ Admin access required."
        )
        return

    requests = load_requests()

    if not requests:

        await query.message.reply_text(
            "📋 No requests found."
        )
        return

    for r in requests:

        text = (
            f"📋 **Request #{r['id']}**\n\n"
            f"👤 Customer: {r['user_name']}\n"
            f"📱 Phone: {r['phone']}\n"
            f"🆔 Account: {r['customer_number']}\n"
            f"🏢 Organization: {r['organization']}\n"
            f"📍 Address: {r['address']}\n\n"
            f"📝 {r['details']}\n\n"
            f"📌 Status: {r['status']}\n"
            f"👨‍🔧 Technician: "
            f"{r['technician_name'] or 'Not assigned'}"
        )

        keyboard = []

        if not r["technician_id"]:

            keyboard.append([
                InlineKeyboardButton(
                    "👨‍🔧 Assign Technician",
                    callback_data=f"assign_{r['id']}"
                )
            ])

        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
            if keyboard else None,
            parse_mode="Markdown"
        )


# =========================================================
# ASSIGN TECHNICIAN
# =========================================================

async def assign_technician(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    if not is_admin(user.id):

        await query.message.reply_text(
            "⛔ Admin access required."
        )
        return

    request_id = int(
        query.data.split("_")[1]
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👨‍🔧 Admin / Technician",
                callback_data=f"tech_{request_id}_{ADMIN_ID}"
            )
        ]
    ])

    await query.message.reply_text(
        f"👨‍🔧 Select technician for Request #{request_id}:",
        reply_markup=keyboard
    )


async def select_technician(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    if not is_admin(user.id):

        await query.message.reply_text(
            "⛔ Admin access required."
        )
        return

    parts = query.data.split("_")

    request_id = int(parts[1])
    technician_id = int(parts[2])

    requests = load_requests()

    request = next(
        (
            r for r in requests
            if int(r["id"]) == request_id
        ),
        None
    )

    if not request:

        await query.message.reply_text(
            "❌ Request not found."
        )
        return

    technician_name = "Admin / Technician"

    request["technician_id"] = technician_id
    request["technician_name"] = technician_name
    request["status"] = "Assigned"

    save_requests(requests)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ Start",
                callback_data=f"start_{request_id}"
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"reject_{request_id}"
            )
        ]
    ])

    await query.message.reply_text(
        f"✅ Request #{request_id} assigned to "
        f"**{technician_name}**.",
        parse_mode="Markdown"
    )

    # Notify technician
    await context.bot.send_message(
        chat_id=technician_id,
        text=(
            f"👨‍🔧 **New Assigned Request**\n\n"
            f"📋 Request: #{request_id}\n"
            f"👤 Customer: {request['user_name']}\n"
            f"📱 Phone: {request['phone']}\n"
            f"📍 Address: {request['address']}\n"
            f"📝 Request:\n{request['details']}\n\n"
            f"📌 Status: Assigned"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    # Notify customer
    await context.bot.send_message(
        chat_id=request["user_id"],
        text=(
            f"👨‍🔧 **Technician Assigned**\n\n"
            f"📋 Request: #{request_id}\n"
            f"👨‍🔧 Technician: {technician_name}\n"
            f"📌 Status: Assigned"
        ),
        parse_mode="Markdown"
    )


# =========================================================
# TECHNICIAN REQUESTS
# =========================================================

async def technician_requests(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    if not is_technician(user.id):

        await query.message.reply_text(
            "⛔ Technician access required."
        )
        return

    requests = load_requests()

    assigned = [
        r for r in requests
        if r["technician_id"] == user.id
        and r["status"] not in ["Completed", "Rejected"]
    ]

    if not assigned:

        await query.message.reply_text(
            "👨‍🔧 You have no active assigned requests."
        )
        return

    for r in assigned:

        keyboard = []

        if r["status"] == "Assigned":

            keyboard.append([
                InlineKeyboardButton(
                    "▶️ Start",
                    callback_data=f"start_{r['id']}"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"reject_{r['id']}"
                )
            ])

        elif r["status"] == "In Progress":

            keyboard.append([
                InlineKeyboardButton(
                    "✅ Complete",
                    callback_data=f"complete_{r['id']}"
                )
            ])

        await query.message.reply_text(
            f"📋 **Request #{r['id']}**\n\n"
            f"👤 Customer: {r['user_name']}\n"
            f"📱 Phone: {r['phone']}\n"
            f"📍 Address: {r['address']}\n"
            f"📝 {r['details']}\n\n"
            f"📌 Status: {r['status']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )


# =========================================================
# START REQUEST
# =========================================================

async def start_assigned_request(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    request_id = int(
        query.data.split("_")[1]
    )

    requests = load_requests()

    request = next(
        (
            r for r in requests
            if int(r["id"]) == request_id
        ),
        None
    )

    if not request:

        await query.message.reply_text(
            "❌ Request not found."
        )
        return

    if request["technician_id"] != user.id:

        await query.message.reply_text(
            "⛔ This request is not assigned to you."
        )
        return

    request["status"] = "In Progress"

    save_requests(requests)

    await query.message.reply_text(
        f"▶️ Request #{request_id} started.\n\n"
        f"Status: **In Progress**",
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=request["user_id"],
        text=(
            f"🔧 **Your request is now being handled.**\n\n"
            f"📋 Request: #{request_id}\n"
            f"📌 Status: In Progress"
        ),
        parse_mode="Markdown"
    )


# =========================================================
# COMPLETE REQUEST
# =========================================================

async def complete_request(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    request_id = int(
        query.data.split("_")[1]
    )

    requests = load_requests()

    request = next(
        (
            r for r in requests
            if int(r["id"]) == request_id
        ),
        None
    )

    if not request:

        await query.message.reply_text(
            "❌ Request not found."
        )
        return

    if request["technician_id"] != user.id:

        await query.message.reply_text(
            "⛔ This request is not assigned to you."
        )
        return

    request["status"] = "Completed"

    save_requests(requests)

    await query.message.reply_text(
        f"✅ **Request #{request_id} completed.**",
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=request["user_id"],
        text=(
            f"✅ **Your request has been completed.**\n\n"
            f"📋 Request: #{request_id}\n"
            f"📌 Status: Completed"
        ),
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"✅ **Request Completed**\n\n"
            f"📋 Request: #{request_id}\n"
            f"👤 Customer: {request['user_name']}\n"
            f"👨‍🔧 Technician: {request['technician_name']}"
        ),
        parse_mode="Markdown"
    )


# =========================================================
# REJECT REQUEST
# =========================================================

async def reject_request(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    request_id = int(
        query.data.split("_")[1]
    )

    requests = load_requests()

    request = next(
        (
            r for r in requests
            if int(r["id"]) == request_id
        ),
        None
    )

    if not request:

        await query.message.reply_text(
            "❌ Request not found."
        )
        return

    if request["technician_id"] != user.id:

        await query.message.reply_text(
            "⛔ This request is not assigned to you."
        )
        return

    request["status"] = "Rejected"

    save_requests(requests)

    await query.message.reply_text(
        f"❌ Request #{request_id} rejected."
    )

    await context.bot.send_message(
        chat_id=request["user_id"],
        text=(
            f"❌ **Your request has been rejected.**\n\n"
            f"📋 Request: #{request_id}\n"
            f"📌 Status: Rejected"
        ),
        parse_mode="Markdown"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"❌ **Request Rejected**\n\n"
            f"📋 Request: #{request_id}\n"
            f"👤 Customer: {request['user_name']}\n"
            f"👨‍🔧 Technician: {request['technician_name']}"
        ),
        parse_mode="Markdown"
    )


# =========================================================
# TECHNICIANS
# =========================================================

async def technicians(update, context):

    query = update.callback_query

    await query.answer()

    await query.message.reply_text(
        "👨‍🔧 **Technicians**\n\n"
        "1. Admin / Technician\n"
        f"Telegram ID: `{ADMIN_ID}`\n"
        "Status: Active",
        parse_mode="Markdown"
    )


# =========================================================
# ACCOUNT
# =========================================================

async def account(update, context):

    query = update.callback_query
    user = update.effective_user

    await query.answer()

    customers = load_customers()

    customer = customers.get(str(user.id))

    if not customer:

        await query.message.reply_text(
            "❌ Account information not found."
        )
        return

    roles = []

    if is_admin(user.id):
        roles.append("👑 Admin")

    if is_technician(user.id):
        roles.append("👨‍🔧 Technician")

    if not roles:
        roles.append("👤 Customer")

    await query.message.reply_text(
        f"👤 **My Account**\n\n"
        f"Name: {customer['full_name'] or 'Not registered'}\n"
        f"📱 Phone: {customer['phone'] or 'Not registered'}\n"
        f"🆔 Customer Number: "
        f"{customer['customer_number'] or 'Not registered'}\n"
        f"🏢 Organization: "
        f"{customer['organization'] or 'Not registered'}\n"
        f"📍 Address: "
        f"{customer['address'] or 'Not registered'}\n"
        f"📧 Email: "
        f"{customer['email'] or 'Not registered'}\n"
        f"🆔 Telegram ID: `{user.id}`\n\n"
        f"Roles: {', '.join(roles)}",
        parse_mode="Markdown"
    )


# =========================================================
# CREDITS
# =========================================================

async def credits(update, context):

    query = update.callback_query

    await query.answer()

    await query.message.reply_text(
        "💰 **My Credits**\n\n"
        "Credits: 0",
        parse_mode="Markdown"
    )


# =========================================================
# CALLBACK ROUTER
# =========================================================

async def button_handler(update, context):

    query = update.callback_query

    data = query.data

    if data == "request":

        await start_request(update, context)

    elif data == "my_requests":

        await my_requests(update, context)

    elif data == "check_request":

        await start_check_request(update, context)

    elif data == "credits":

        await credits(update, context)

    elif data == "account":

        await account(update, context)

    elif data == "all_requests":

        await all_requests(update, context)

    elif data == "technicians":

        await technicians(update, context)

    elif data == "technician_requests":

        await technician_requests(update, context)

    elif data.startswith("assign_"):

        await assign_technician(update, context)

    elif data.startswith("tech_"):

        await select_technician(update, context)

    elif data.startswith("start_"):

        await start_assigned_request(update, context)

    elif data.startswith("complete_"):

        await complete_request(update, context)

    elif data.startswith("reject_"):

        await reject_request(update, context)


# =========================================================
# TEXT MESSAGE ROUTER
# =========================================================

async def handle_text(update, context):

    if context.user_data.get("registering"):

        await process_registration(update, context)
        return

    if context.user_data.get("creating_request"):

        await receive_request(update, context)
        return

    if context.user_data.get("checking_request"):

        await receive_check(update, context)
        return

    await update.message.reply_text(
        "Please use /start and select an option."
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN environment variable is not set."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    # Inline buttons
    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # All normal text messages
    # IMPORTANT: Only ONE text handler
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    print("Telegram bot is running...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
