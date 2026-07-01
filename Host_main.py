# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import sqlite3
import logging
import threading
import sys
import atexit

from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return f"""<h1>✅ Upload Bot is Running</h1>
<p>Users: {len(active_users)}</p>
<p>Running Scripts: {len(bot_scripts)}</p>
<p>Status: Online</p>"""

@app.route("/health")
def health():
    return {
        "status": "running",
        "active_scripts": len(bot_scripts),
        "users": len(active_users)
    }

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# --- Configuration ---
TOKEN = 'YOUR_BOT_TOKEN'
OWNER_ID = ''   #YOUR USER ID
ADMIN_ID = ''   #ADMIN OR YOUR USER ID 
YOUR_USERNAME = 'nox_shadowx'
UPDATE_CHANNEL = 'https://t.me/Music_Brigade_Chatting_zone'

# Folder setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# File limits
FREE_USER_LIMIT = 1
SUBSCRIBED_USER_LIMIT = 10
ADMIN_LIMIT = 20
OWNER_LIMIT = float('inf')

# Create directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# Data structures
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False

# Logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_files
                 (user_id INTEGER, file_name TEXT, file_type TEXT,
                  PRIMARY KEY (user_id, file_name))''')
    c.execute('''CREATE TABLE IF NOT EXISTS active_users
                 (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (user_id INTEGER PRIMARY KEY)''')
    c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
    if ADMIN_ID != OWNER_ID:
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
    conn.commit()
    conn.close()

def load_data():
    global user_subscriptions, user_files, active_users, admin_ids
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    
    c.execute('SELECT user_id, expiry FROM subscriptions')
    for user_id, expiry in c.fetchall():
        try:
            user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
        except:
            pass
    
    c.execute('SELECT user_id, file_name, file_type FROM user_files')
    for user_id, file_name, file_type in c.fetchall():
        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id].append((file_name, file_type))
    
    c.execute('SELECT user_id FROM active_users')
    active_users.update(user_id for (user_id,) in c.fetchall())
    
    c.execute('SELECT user_id FROM admins')
    admin_ids.update(user_id for (user_id,) in c.fetchall())
    
    conn.close()

init_db()
load_data()

# --- Helper Functions ---
def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_limit(user_id):
    if user_id == OWNER_ID:
        return OWNER_LIMIT
    if user_id in admin_ids:
        return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            if script_info['process'].poll() is None:
                return True
            else:
                if 'log_file' in script_info and script_info['log_file']:
                    try:
                        script_info['log_file'].close()
                    except:
                        pass
                if script_key in bot_scripts:
                    del bot_scripts[script_key]
                return False
        except:
            return False
    return False

def kill_process(process_info):
    try:
        if 'log_file' in process_info and process_info['log_file']:
            try:
                process_info['log_file'].close()
            except:
                pass
        if process_info.get('process'):
            process_info['process'].terminate()
            time.sleep(1)
            if process_info['process'].poll() is None:
                process_info['process'].kill()
    except:
        pass

# --- Button Layouts ---
COMMAND_BUTTONS_USER = [
    ["📢 Updates Channel"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "📊 Statistics"],
    ["📞 Contact Owner"]
]

COMMAND_BUTTONS_ADMIN = [
    ["📢 Updates Channel"],
    ["📤 Upload File", "📂 Check Files"],
    ["⚡ Bot Speed", "📊 Statistics"],
    ["💳 Subscriptions", "📢 Broadcast"],
    ["🔒 Lock Bot", "🟢 Running All Code"],
    ["👑 Admin Panel", "📞 Contact Owner"]
]

def get_reply_keyboard(user_id):
    layout = COMMAND_BUTTONS_ADMIN if user_id in admin_ids else COMMAND_BUTTONS_USER
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in layout:
        markup.add(*[types.KeyboardButton(text) for text in row])
    return markup

def get_inline_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton('📢 Updates Channel', url=UPDATE_CHANNEL))
    markup.add(types.InlineKeyboardButton('📤 Upload File', callback_data='upload'),
               types.InlineKeyboardButton('📂 Check Files', callback_data='check_files'))
    markup.add(types.InlineKeyboardButton('⚡ Bot Speed', callback_data='speed'),
               types.InlineKeyboardButton('📊 Statistics', callback_data='stats'))
    markup.add(types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME}'))
    
    if user_id in admin_ids:
        markup.add(types.InlineKeyboardButton('💳 Subscriptions', callback_data='subscription'),
                   types.InlineKeyboardButton('📢 Broadcast', callback_data='broadcast'))
        lock_text = '🔒 Lock Bot' if not bot_locked else '🔓 Unlock Bot'
        markup.add(types.InlineKeyboardButton(lock_text, callback_data='lock_bot' if not bot_locked else 'unlock_bot'),
                   types.InlineKeyboardButton('🟢 Running All Code', callback_data='run_all_scripts'))
        markup.add(types.InlineKeyboardButton('👑 Admin Panel', callback_data='admin_panel'))
    
    return markup

def create_control_buttons(script_owner_id, file_name, is_running):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.add(types.InlineKeyboardButton("🔴 Stop", callback_data=f'stop_{script_owner_id}_{file_name}'),
                   types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{script_owner_id}_{file_name}'))
    else:
        markup.add(types.InlineKeyboardButton("🟢 Start", callback_data=f'start_{script_owner_id}_{file_name}'))
    markup.add(types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}'),
               types.InlineKeyboardButton("📜 Logs", callback_data=f'logs_{script_owner_id}_{file_name}'))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='check_files'))
    return markup

# --- Database Operations ---
def save_user_file(user_id, file_name, file_type):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)',
              (user_id, file_name, file_type))
    conn.commit()
    conn.close()
    if user_id not in user_files:
        user_files[user_id] = []
    user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
    user_files[user_id].append((file_name, file_type))

def remove_user_file_db(user_id, file_name):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
    conn.commit()
    conn.close()
    if user_id in user_files:
        user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
        if not user_files[user_id]:
            del user_files[user_id]

def add_active_user(user_id):
    active_users.add(user_id)
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def save_subscription(user_id, expiry):
    expiry_str = expiry.isoformat()
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', (user_id, expiry_str))
    conn.commit()
    conn.close()
    user_subscriptions[user_id] = {'expiry': expiry}

def remove_subscription_db(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    if user_id in user_subscriptions:
        del user_subscriptions[user_id]

def add_admin_db(admin_id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
    conn.commit()
    conn.close()
    admin_ids.add(admin_id)

def remove_admin_db(admin_id):
    if admin_id == OWNER_ID:
        return False
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
    conn.commit()
    conn.close()
    admin_ids.discard(admin_id)
    return True

# --- Script Running Functions ---
def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply):
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Script '{file_name}' not found!")
            remove_user_file_db(script_owner_id, file_name)
            return
        
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE
        )
        
        script_key = f"{script_owner_id}_{file_name}"
        bot_scripts[script_key] = {
            'process': process,
            'log_file': log_file,
            'file_name': file_name,
            'script_owner_id': script_owner_id,
            'start_time': datetime.now(),
            'user_folder': user_folder
        }
        
        bot.reply_to(message_obj_for_reply, f"✅ Script '{file_name}' started! (PID: {process.pid})")
        
    except Exception as e:
        bot.reply_to(message_obj_for_reply, f"❌ Error starting script: {str(e)}")

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply):
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj_for_reply, f"❌ Script '{file_name}' not found!")
            remove_user_file_db(script_owner_id, file_name)
            return
        
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        
        process = subprocess.Popen(
            ['node', script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE
        )
        
        script_key = f"{script_owner_id}_{file_name}"
        bot_scripts[script_key] = {
            'process': process,
            'log_file': log_file,
            'file_name': file_name,
            'script_owner_id': script_owner_id,
            'start_time': datetime.now(),
            'user_folder': user_folder
        }
        
        bot.reply_to(message_obj_for_reply, f"✅ JS Script '{file_name}' started! (PID: {process.pid})")
        
    except FileNotFoundError:
        bot.reply_to(message_obj_for_reply, "❌ Node.js not found! Please install Node.js")
    except Exception as e:
        bot.reply_to(message_obj_for_reply, f"❌ Error starting JS script: {str(e)}")

# --- File Handling ---
def handle_zip_file(zip_content, zip_name, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        zip_path = os.path.join(temp_dir, zip_name)
        
        with open(zip_path, 'wb') as f:
            f.write(zip_content)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find main script
        py_files = [f for f in os.listdir(temp_dir) if f.endswith('.py')]
        js_files = [f for f in os.listdir(temp_dir) if f.endswith('.js')]
        
        main_script = None
        file_type = None
        
        for name in ['main.py', 'bot.py', 'app.py']:
            if name in py_files:
                main_script = name
                file_type = 'py'
                break
        
        if not main_script:
            for name in ['index.js', 'main.js', 'bot.js']:
                if name in js_files:
                    main_script = name
                    file_type = 'js'
                    break
        
        if not main_script and py_files:
            main_script = py_files[0]
            file_type = 'py'
        elif not main_script and js_files:
            main_script = js_files[0]
            file_type = 'js'
        
        if not main_script:
            bot.reply_to(message, "❌ No Python or JavaScript script found in ZIP!")
            return
        
        # Move files to user folder
        for item in os.listdir(temp_dir):
            src = os.path.join(temp_dir, item)
            dst = os.path.join(user_folder, item)
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            shutil.move(src, dst)
        
        save_user_file(user_id, main_script, file_type)
        main_script_path = os.path.join(user_folder, main_script)
        
        bot.reply_to(message, f"✅ Extracted ZIP. Starting {main_script}...")
        
        if file_type == 'py':
            threading.Thread(target=run_script, args=(main_script_path, user_id, user_folder, main_script, message)).start()
        else:
            threading.Thread(target=run_js_script, args=(main_script_path, user_id, user_folder, main_script, message)).start()
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error processing ZIP: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

# --- Command Handlers ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    
    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, "⚠️ Bot locked by admin. Try later.")
        return
    
    if user_id not in active_users:
        add_active_user(user_id)
        try:
            bot.send_message(OWNER_ID, f"🎉 New user!\nName: {user_name}\nID: `{user_id}`", parse_mode='Markdown')
        except:
            pass
    
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
    
    if user_id == OWNER_ID:
        status = "👑 Owner"
    elif user_id in admin_ids:
        status = "🛡️ Admin"
    elif user_id in user_subscriptions:
        expiry = user_subscriptions[user_id].get('expiry')
        if expiry and expiry > datetime.now():
            days_left = (expiry - datetime.now()).days
            status = f"⭐ Premium ({days_left} days left)"
        else:
            status = "🆓 Free User"
            remove_subscription_db(user_id)
    else:
        status = "🆓 Free User"
    
    welcome_msg = (f"〽️ Welcome, {user_name}!\n\n🆔 ID: `{user_id}`\n"
                   f"🔰 Status: {status}\n📁 Files: {current_files} / {limit_str}\n\n"
                   f"Send `.py`, `.js`, or `.zip` files to host and run them!")
    
    bot.send_message(chat_id, welcome_msg, reply_markup=get_reply_keyboard(user_id), parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📢 Updates Channel")
def updates_channel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📢 Updates Channel', url=UPDATE_CHANNEL))
    bot.reply_to(message, "Join our Updates Channel:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📤 Upload File")
def upload_file(message):
    user_id = message.from_user.id
    
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked, cannot accept files.")
        return
    
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ File limit reached ({current_files}/{limit_str}). Delete files first.")
        return
    
    bot.reply_to(message, "📤 Send your Python (.py), JavaScript (.js), or ZIP (.zip) file.")

@bot.message_handler(func=lambda message: message.text == "📂 Check Files")
def check_files(message):
    user_id = message.from_user.id
    user_files_list = user_files.get(user_id, [])
    
    if not user_files_list:
        bot.reply_to(message, "📂 No files uploaded yet.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(user_files_list):
        is_running = is_bot_running(user_id, file_name)
        status = "🟢 Running" if is_running else "🔴 Stopped"
        btn_text = f"{file_name} ({file_type}) - {status}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'file_{user_id}_{file_name}'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
    bot.reply_to(message, "📂 Your files:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "⚡ Bot Speed")
def bot_speed(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    start = time.time()
    msg = bot.reply_to(message, "🏃 Testing speed...")
    response_time = round((time.time() - start) * 1000, 2)
    
    status = "🔒 Locked" if bot_locked else "🔓 Unlocked"
    
    if user_id == OWNER_ID:
        level = "👑 Owner"
    elif user_id in admin_ids:
        level = "🛡️ Admin"
    elif user_id in user_subscriptions:
        level = "⭐ Premium"
    else:
        level = "🆓 Free User"
    
    speed_msg = f"⚡ Bot Speed\n\nResponse: {response_time} ms\nStatus: {status}\nLevel: {level}"
    bot.edit_message_text(speed_msg, chat_id, msg.message_id)

@bot.message_handler(func=lambda message: message.text == "📊 Statistics")
def statistics(message):
    user_id = message.from_user.id
    
    total_users = len(active_users)
    total_files = sum(len(files) for files in user_files.values())
    running_bots = len(bot_scripts)
    
    stats_msg = f"📊 Statistics\n\n👥 Users: {total_users}\n📁 Files: {total_files}\n🟢 Running: {running_bots}"
    
    if user_id in admin_ids:
        stats_msg += f"\n🔒 Bot Locked: {bot_locked}"
    
    bot.reply_to(message, stats_msg)

@bot.message_handler(func=lambda message: message.text == "📞 Contact Owner")
def contact_owner(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME}'))
    bot.reply_to(message, "Contact Owner:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "💳 Subscriptions")
def subscriptions_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin required.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton('➕ Add', callback_data='add_subscription'),
               types.InlineKeyboardButton('➖ Remove', callback_data='remove_subscription'))
    markup.add(types.InlineKeyboardButton('🔍 Check', callback_data='check_subscription'))
    markup.add(types.InlineKeyboardButton('🔙 Back', callback_data='back_to_main'))
    bot.reply_to(message, "💳 Subscription Management:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📢 Broadcast")
def broadcast(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin required.")
        return
    
    msg = bot.reply_to(message, "📢 Send message to broadcast.\n/cancel to cancel.")
    bot.register_next_step_handler(msg, process_broadcast)

@bot.message_handler(func=lambda message: message.text == "🔒 Lock Bot")
def lock_bot(message):
    global bot_locked
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin required.")
        return
    
    bot_locked = True
    bot.reply_to(message, "🔒 Bot locked.")

@bot.message_handler(func=lambda message: message.text == "🟢 Running All Code")
def run_all_scripts(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin required.")
        return
    
    bot.reply_to(message, "🔄 Starting all scripts...")
    started = 0
    
    for user_id, files in user_files.items():
        user_folder = get_user_folder(user_id)
        for file_name, file_type in files:
            if not is_bot_running(user_id, file_name):
                file_path = os.path.join(user_folder, file_name)
                if os.path.exists(file_path):
                    try:
                        if file_type == 'py':
                            threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, message)).start()
                        else:
                            threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, message)).start()
                        started += 1
                        time.sleep(0.5)
                    except:
                        pass
    
    bot.send_message(message.chat.id, f"✅ Started {started} scripts.")

@bot.message_handler(func=lambda message: message.text == "👑 Admin Panel")
def admin_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin required.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton('➕ Add Admin', callback_data='add_admin'),
               types.InlineKeyboardButton('➖ Remove Admin', callback_data='remove_admin'))
    markup.add(types.InlineKeyboardButton('📋 List Admins', callback_data='list_admins'))
    markup.add(types.InlineKeyboardButton('🔙 Back', callback_data='back_to_main'))
    bot.reply_to(message, "👑 Admin Panel:", reply_markup=markup)

# --- File Upload Handler ---
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    doc = message.document
    file_name = doc.file_name
    
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot locked.")
        return
    
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ File limit reached ({current_files}/{limit_str}).")
        return
    
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "❌ Only .py, .js, .zip files allowed.")
        return
    
    if doc.file_size > 20 * 1024 * 1024:
        bot.reply_to(message, "❌ File too large (max 20MB).")
        return
    
    try:
        bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
        
        msg = bot.reply_to(message, f"⏳ Downloading {file_name}...")
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        bot.edit_message_text(f"✅ Downloaded. Processing...", message.chat.id, msg.message_id)
        
        if ext == '.zip':
            handle_zip_file(downloaded, file_name, message)
        else:
            user_folder = get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            with open(file_path, 'wb') as f:
                f.write(downloaded)
            
            save_user_file(user_id, file_name, ext[1:])
            
            if ext == '.py':
                threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, message)).start()
            else:
                threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, message)).start()
            
            bot.send_message(message.chat.id, f"✅ {file_name} uploaded and starting...")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Callback Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    global bot_locked
    user_id = call.from_user.id
    data = call.data
    
    if bot_locked and user_id not in admin_ids:
        bot.answer_callback_query(call.id, "Bot locked.", show_alert=True)
        return
    
    try:
        if data == 'back_to_main':
            bot.edit_message_text("Main Menu", call.message.chat.id, call.message.message_id,
                                 reply_markup=get_inline_menu(user_id))
            bot.answer_callback_query(call.id)
        
        elif data == 'upload':
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "📤 Send your file.")
        
        elif data == 'check_files':
            user_files_list = user_files.get(user_id, [])
            if not user_files_list:
                bot.answer_callback_query(call.id, "No files", show_alert=True)
                return
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            for file_name, file_type in sorted(user_files_list):
                is_running = is_bot_running(user_id, file_name)
                status = "🟢" if is_running else "🔴"
                markup.add(types.InlineKeyboardButton(f"{status} {file_name} ({file_type})", 
                                                     callback_data=f'file_{user_id}_{file_name}'))
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
            bot.edit_message_text("Select file:", call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)
        
        elif data == 'speed':
            user_id_cb = call.from_user.id
            start = time.time()
            bot.answer_callback_query(call.id)
            response_time = round((time.time() - start) * 1000, 2)
            
            status = "🔒 Locked" if bot_locked else "🔓 Unlocked"
            
            if user_id_cb == OWNER_ID:
                level = "👑 Owner"
            elif user_id_cb in admin_ids:
                level = "🛡️ Admin"
            elif user_id_cb in user_subscriptions:
                level = "⭐ Premium"
            else:
                level = "🆓 Free User"
            
            speed_msg = f"⚡ Bot Speed\n\nResponse: {response_time} ms\nStatus: {status}\nLevel: {level}"
            bot.edit_message_text(speed_msg, call.message.chat.id, call.message.message_id, reply_markup=get_inline_menu(user_id_cb))
        
        elif data == 'stats':
            bot.answer_callback_query(call.id)
            statistics(call.message)
        
        elif data.startswith('file_'):
            _, owner_id, file_name = data.split('_', 2)
            owner_id = int(owner_id)
            
            if user_id != owner_id and user_id not in admin_ids:
                bot.answer_callback_query(call.id, "Not your file!", show_alert=True)
                return
            
            is_running = is_bot_running(owner_id, file_name)
            markup = create_control_buttons(owner_id, file_name, is_running)
            bot.edit_message_text(f"Manage: {file_name}", call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)
        
        elif data.startswith('start_'):
            _, owner_id, file_name = data.split('_', 2)
            owner_id = int(owner_id)
            
            if user_id != owner_id and user_id not in admin_ids:
                bot.answer_callback_query(call.id, "Permission denied", show_alert=True)
                return
            
            if is_bot_running(owner_id, file_name):
                bot.answer_callback_query(call.id, "Already running", show_alert=True)
                return
            
            user_folder = get_user_folder(owner_id)
            file_path = os.path.join(user_folder, file_name)
            file_type = None
            
            for fn, ft in user_files.get(owner_id, []):
                if fn == file_name:
                    file_type = ft
                    break
            
            bot.answer_callback_query(call.id, f"Starting {file_name}...")
            
            if file_type == 'py':
                threading.Thread(target=run_script, args=(file_path, owner_id, user_folder, file_name, call.message)).start()
            else:
                threading.Thread(target=run_js_script, args=(file_path, owner_id, user_folder, file_name, call.message)).start()
            
            time.sleep(1)
            is_running = is_bot_running(owner_id, file_name)
            markup = create_control_buttons(owner_id, file_name, is_running)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        
        elif data.startswith('stop_'):
            _, owner_id, file_name = data.split('_', 2)
            owner_id = int(owner_id)
            
            if user_id != owner_id and user_id not in admin_ids:
                bot.answer_callback_query(call.id, "Permission denied", show_alert=True)
                return
            
            script_key = f"{owner_id}_{file_name}"
            if script_key in bot_scripts:
                kill_process(bot_scripts[script_key])
                del bot_scripts[script_key]
                bot.answer_callback_query(call.id, f"Stopped {file_name}")
            else:
                bot.answer_callback_query(call.id, "Not running", show_alert=True)
            
            markup = create_control_buttons(owner_id, file_name, False)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        
        elif data.startswith('restart_'):
            _, owner_id, file_name = data.split('_', 2)
            owner_id = int(owner_id)
            
            script_key = f"{owner_id}_{file_name}"
            if script_key in bot_scripts:
                kill_process(bot_scripts[script_key])
                del bot_scripts[script_key]
                time.sleep(1)
            
            user_folder = get_user_folder(owner_id)
            file_path = os.path.join(user_folder, file_name)
            file_type = None
            
            for fn, ft in user_files.get(owner_id, []):
                if fn == file_name:
                    file_type = ft
                    break
            
            bot.answer_callback_query(call.id, f"Restarting {file_name}...")
            
            if file_type == 'py':
                threading.Thread(target=run_script, args=(file_path, owner_id, user_folder, file_name, call.message)).start()
            else:
                threading.Thread(target=run_js_script, args=(file_path, owner_id, user_folder, file_name, call.message)).start()
        
        elif data.startswith('delete_'):
            _, owner_id, file_name = data.split('_', 2)
            owner_id = int(owner_id)
            
            if user_id != owner_id and user_id not in admin_ids:
                bot.answer_callback_query(call.id, "Permission denied", show_alert=True)
                return
            
            script_key = f"{owner_id}_{file_name}"
            if script_key in bot_scripts:
                kill_process(bot_scripts[script_key])
                del bot_scripts[script_key]
            
            user_folder = get_user_folder(owner_id)
            file_path = os.path.join(user_folder, file_name)
            log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
            
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(log_path):
                os.remove(log_path)
            
            remove_user_file_db(owner_id, file_name)
            bot.answer_callback_query(call.id, f"Deleted {file_name}")
            bot.edit_message_text(f"✅ Deleted {file_name}", call.message.chat.id, call.message.message_id)
        
        elif data.startswith('logs_'):
            _, owner_id, file_name = data.split('_', 2)
            owner_id = int(owner_id)
            
            if user_id != owner_id and user_id not in admin_ids:
                bot.answer_callback_query(call.id, "Permission denied", show_alert=True)
                return
            
            user_folder = get_user_folder(owner_id)
            log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
            
            if not os.path.exists(log_path):
                bot.answer_callback_query(call.id, "No logs", show_alert=True)
                return
            
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()[-3000:]
            
            if not log_content.strip():
                log_content = "(empty)"
            
            bot.send_message(call.message.chat.id, f"📜 Logs for {file_name}:\n```\n{log_content}\n```", parse_mode='Markdown')
            bot.answer_callback_query(call.id)
        
        elif data == 'subscription' and user_id in admin_ids:
            bot.answer_callback_query(call.id)
            subscriptions_panel(call.message)
        
        elif data == 'lock_bot' and user_id in admin_ids:
            bot_locked = True
            bot.answer_callback_query(call.id, "Bot locked")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                         reply_markup=get_inline_menu(user_id))
        
        elif data == 'unlock_bot' and user_id in admin_ids:
            bot_locked = False
            bot.answer_callback_query(call.id, "Bot unlocked")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                         reply_markup=get_inline_menu(user_id))
        
        elif data == 'broadcast' and user_id in admin_ids:
            bot.answer_callback_query(call.id)
            broadcast(call.message)
        
        elif data == 'run_all_scripts' and user_id in admin_ids:
            bot.answer_callback_query(call.id)
            run_all_scripts(call.message)
        
        elif data == 'admin_panel' and user_id in admin_ids:
            bot.answer_callback_query(call.id)
            admin_panel(call.message)
        
        elif data == 'add_admin' and user_id == OWNER_ID:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(call.message.chat.id, "Send user ID to add as admin:")
            bot.register_next_step_handler(msg, process_add_admin)
        
        elif data == 'remove_admin' and user_id == OWNER_ID:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(call.message.chat.id, "Send user ID to remove admin:")
            bot.register_next_step_handler(msg, process_remove_admin)
        
        elif data == 'list_admins' and user_id in admin_ids:
            admin_list = []
            for aid in sorted(admin_ids):
                role = "👑 Owner" if aid == OWNER_ID else "🛡️ Admin"
                admin_list.append(f"{role}: `{aid}`")
            bot.edit_message_text("👑 Admins:\n\n" + "\n".join(admin_list), 
                                 call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            bot.answer_callback_query(call.id)
        
        elif data == 'add_subscription' and user_id in admin_ids:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(call.message.chat.id, "Send: `user_id days`\nExample: `123456789 30`", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_add_subscription)
        
        elif data == 'remove_subscription' and user_id in admin_ids:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(call.message.chat.id, "Send user ID to remove subscription:")
            bot.register_next_step_handler(msg, process_remove_subscription)
        
        elif data == 'check_subscription' and user_id in admin_ids:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(call.message.chat.id, "Send user ID to check subscription:")
            bot.register_next_step_handler(msg, process_check_subscription)
        
        else:
            bot.answer_callback_query(call.id, "Unknown action")
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "Error", show_alert=True)

# --- Admin Processing Functions ---
def process_add_admin(message):
    if message.from_user.id != OWNER_ID:
        return
    
    if message.text.lower() == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    
    try:
        user_id = int(message.text.strip())
        if user_id in admin_ids:
            bot.reply_to(message, "Already admin.")
            return
        
        add_admin_db(user_id)
        bot.reply_to(message, f"✅ Added admin: `{user_id}`")
        try:
            bot.send_message(user_id, "🎉 You are now an admin!")
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID.")

def process_remove_admin(message):
    if message.from_user.id != OWNER_ID:
        return
    
    if message.text.lower() == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    
    try:
        user_id = int(message.text.strip())
        if user_id == OWNER_ID:
            bot.reply_to(message, "Cannot remove owner.")
            return
        
        if remove_admin_db(user_id):
            bot.reply_to(message, f"✅ Removed admin: `{user_id}`")
        else:
            bot.reply_to(message, "Not an admin.")
    except:
        bot.reply_to(message, "❌ Invalid user ID.")

def process_add_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    
    if message.text.lower() == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError()
        
        user_id = int(parts[0])
        days = int(parts[1])
        
        current = user_subscriptions.get(user_id, {}).get('expiry')
        if current and current > datetime.now():
            new_expiry = current + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
        
        save_subscription(user_id, new_expiry)
        bot.reply_to(message, f"✅ Added {days} days for user `{user_id}`\nExpires: {new_expiry.strftime('%Y-%m-%d')}")
        
        try:
            bot.send_message(user_id, f"🎉 Subscription extended by {days} days!")
        except:
            pass
    except:
        bot.reply_to(message, "❌ Use: `user_id days`", parse_mode='Markdown')

def process_remove_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    
    if message.text.lower() == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    
    try:
        user_id = int(message.text.strip())
        remove_subscription_db(user_id)
        bot.reply_to(message, f"✅ Removed subscription for `{user_id}`")
    except:
        bot.reply_to(message, "❌ Invalid user ID.")

def process_check_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    
    if message.text.lower() == '/cancel':
        bot.reply_to(message, "Cancelled.")
        return
    
    try:
        user_id = int(message.text.strip())
        if user_id in user_subscriptions:
            expiry = user_subscriptions[user_id]['expiry']
            if expiry > datetime.now():
                days = (expiry - datetime.now()).days
                bot.reply_to(message, f"✅ User `{user_id}` has active subscription\nExpires: {expiry.strftime('%Y-%m-%d')}\nDays left: {days}")
            else:
                bot.reply_to(message, f"⚠️ Subscription expired for `{user_id}`")
                remove_subscription_db(user_id)
        else:
            bot.reply_to(message, f"ℹ️ No subscription for `{user_id}`")
    except:
        bot.reply_to(message, "❌ Invalid user ID.")

def process_broadcast(message):
    if message.from_user.id not in admin_ids:
        return
    
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "Broadcast cancelled.")
        return
    
    bot.broadcast_msg = message
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Confirm", callback_data="confirm_broadcast"),
               types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast"))
    
    preview = message.text[:200] if message.text else "(Media)"
    bot.reply_to(message, f"⚠️ Send to {len(active_users)} users:\n\n{preview}\n\nConfirm?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_broadcast', 'cancel_broadcast'])
def handle_broadcast_confirm(call):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "Admin only", show_alert=True)
        return
    
    if call.data == 'cancel_broadcast':
        bot.answer_callback_query(call.id, "Cancelled")
        bot.edit_message_text("Broadcast cancelled.", call.message.chat.id, call.message.message_id)
        return
    
    bot.answer_callback_query(call.id, "Starting broadcast...")
    bot.edit_message_text("📢 Broadcasting...", call.message.chat.id, call.message.message_id)
    
    broadcast_msg = getattr(bot, 'broadcast_msg', None)
    if broadcast_msg:
        threading.Thread(target=execute_broadcast, args=(broadcast_msg, call.message.chat.id)).start()

def execute_broadcast(broadcast_msg, admin_chat_id):
    sent = 0
    failed = 0
    
    for user_id in active_users:
        try:
            if broadcast_msg.text:
                bot.send_message(user_id, broadcast_msg.text)
            elif broadcast_msg.photo:
                bot.send_photo(user_id, broadcast_msg.photo[-1].file_id, caption=broadcast_msg.caption)
            sent += 1
        except:
            failed += 1
        time.sleep(0.05)
    
    bot.send_message(admin_chat_id, f"✅ Broadcast done!\nSent: {sent}\nFailed: {failed}")

# --- Cleanup ---
def cleanup():
    for key, info in bot_scripts.items():
        try:
            kill_process(info)
        except:
            pass

atexit.register(cleanup)

# --- Main ---
if __name__ == '__main__':
    print("=" * 50)
    print("Bot Starting...")
    print(f"Owner ID: {OWNER_ID}")
    print(f"Admins: {admin_ids}")
    print("=" * 50)
    
    # Flask keep-alive removed for Termux
    
    threading.Thread(target=run_web, daemon=True).start()

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
