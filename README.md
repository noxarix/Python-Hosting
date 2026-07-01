# 🤖 Python-Hosting Bot

A powerful **Telegram bot** that allows users to upload and run Python and JavaScript scripts directly through the bot interface. Perfect for hosting and managing small scripts, bots, and applications in the cloud!

---

## ✨ Features

### 👤 User Features
- **📤 Upload Files** - Upload `.py`, `.js`, or `.zip` files to run
- **📂 File Management** - View, start, stop, and delete your uploaded scripts
- **🟢 Script Control** - Start, stop, and restart scripts on demand
- **📊 Statistics** - View bot performance and active scripts
- **📜 Logs Viewer** - Monitor script output and debug errors
- **⚡ Speed Test** - Check bot response time

### 🛡️ Admin Features
- **💳 Subscription Management** - Add/remove premium subscriptions for users
- **📢 Broadcast Messages** - Send messages to all users
- **🔒 Bot Lock** - Lock/unlock the bot for all non-admin users
- **🟢 Run All Scripts** - Start all uploaded scripts simultaneously
- **👑 Admin Panel** - Manage admins and permissions

### 💰 User Tiers
- **🆓 Free Users** - 1 file limit
- **⭐ Premium Users** - 10 file limit (with active subscription)
- **🛡️ Admin** - 20 file limit
- **👑 Owner** - Unlimited files

---

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- Node.js (for running `.js` files)
- pip (Python package manager)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/noxarix/Python-Hosting.git
cd Python-Hosting
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure the bot**
Edit `Host_main.py` and update:
```python
TOKEN = 'YOUR_BOT_TOKEN'  # Your Telegram bot token
OWNER_ID = OWNER_USERID  # Your Telegram user ID
ADMIN_ID = ADMIN_USERID  # Admin user ID
YOUR_USERNAME = 'OWNER_USERNAME'  # Your Telegram username
UPDATE_CHANNEL = 'https://t.me/Your_Channel'  # Your update channel
```

4. **Run the bot**
```bash
python Host_main.py
```

---

## 📦 Requirements

```
pyTelegramBotAPI  # Telegram bot API wrapper
Flask             # Web framework for health checks
```

---

## 🎮 Usage

### For Users

1. **Start the bot** - Send `/start` to get welcome message
2. **Upload a file** - Click "📤 Upload File" and send your `.py`, `.js`, or `.zip` file
3. **Manage files** - Click "📂 Check Files" to see all your scripts
4. **Control scripts** - Use buttons to Start, Stop, Restart, or Delete scripts
5. **View logs** - Click "📜 Logs" to see script output

### For Admins

- **💳 Subscriptions** - Add/remove premium subscriptions
- **📢 Broadcast** - Send notifications to all users
- **🔒 Lock Bot** - Prevent non-admins from uploading files
- **👑 Admin Panel** - Manage admin permissions

---

## 📁 File Structure

```
Python-Hosting/
├── Host_main.py       # Main bot application
├── requirements.txt   # Python dependencies
├── upload_bots/       # User script storage directory
├── inf/               # Database directory
│   └── bot_data.db    # SQLite database
└── README.md          # This file
```

---

## 💾 Database

The bot uses **SQLite** to store:
- User subscriptions and expiry dates
- User file information
- Active users list
- Admin permissions

Database location: `inf/bot_data.db`

---

## 🔧 API & Health Check

The bot includes a **Flask web server** for health monitoring:

- **GET `/`** - Returns bot status and statistics
- **GET `/health`** - Returns JSON health status
- **Port** - `10000` (or `PORT` environment variable)

---

## ⚙️ Configuration

### File Limits
```python
FREE_USER_LIMIT = 1           # Free users can upload 1 file
SUBSCRIBED_USER_LIMIT = 10    # Premium users can upload 10 files
ADMIN_LIMIT = 20              # Admins can upload 20 files
OWNER_LIMIT = float('inf')    # Owner has unlimited files
```

### File Size Limit
- Maximum file size: **20 MB**

### Supported File Types
- `.py` - Python scripts
- `.js` - JavaScript scripts (requires Node.js)
- `.zip` - ZIP archives (auto-extracts)

---

## 🎯 Automatic ZIP Handling

When you upload a `.zip` file, the bot:
1. Extracts the contents
2. Searches for a main script:
   - Python: `main.py`, `bot.py`, or `app.py`
   - JavaScript: `index.js`, `main.js`, or `bot.js`
3. Automatically starts the main script
4. Falls back to the first found script if no match

---

## 📝 Logging

- **Script logs** stored in user folders: `upload_bots/{user_id}/{filename}.log`
- **Bot logs** displayed in console
- **Log limit** - Last 3000 characters shown via bot

---

## 🛡️ Security Features

- **User isolation** - Each user gets a separate folder
- **Permission checks** - Users can only access their files
- **Bot lock feature** - Admin can prevent non-admin file uploads
- **Admin verification** - Most operations require admin/owner status

---

## 🐛 Troubleshooting

### Bot not responding
- Check if bot token is valid
- Ensure internet connection
- Check bot logs for errors

### Files not running
- Verify file format (`.py` or `.js`)
- Check file permissions
- View logs for error messages
- For `.js` files, ensure Node.js is installed

### Node.js not found
- Install Node.js: https://nodejs.org/
- Ensure `node` command is in PATH

---

## 📞 Support

For issues or questions:
- 📧 Contact via Telegram (see `YOUR_USERNAME` in config)
- 📢 Join updates channel for announcements

---

## 📄 License

This project is open source and available for personal use.

---

## ⚠️ Disclaimer

This bot allows execution of user-provided code. Ensure:
- You trust the scripts being uploaded
- You run this in a secure environment
- You monitor server resources

---

**Made with ❤️ by noxarix**
