import os
import time
from datetime import datetime
import telebot
from telebot import types
from pymongo import MongoClient

# === CONFIG ===
TOKEN = os.getenv("TOKEN") or "7869962843:AAGYUWT0o0_E-ysKFfmRGWqGQozcOPb3FYg"
CHANNEL = os.getenv("CHANNEL") or "@takakeepercom"
MONGO_URI = os.getenv("MONGO_URI") or "mongodb+srv://takakeeper:sr@@http://95850270@takakeeper.96qzkoi.mongodb.net/?retryWrites=true&w=majority&appName=TakaKeeper"
ADMIN_ID = 7279163908  # নিজের টেলিগ্রাম আইডি দিন (@userinfobot দিয়ে দেখে নিন)

bot = telebot.TeleBot(TOKEN)
client = MongoClient(MONGO_URI)
db = client['earnBotDB']
users = db['users']
task_logs = db['task_logs']
ads = db['ads']  # Task গুলোর জন্য আলাদা কালেকশন

# === START COMMAND ===
@bot.message_handler(commands=['start'])
def start_handler(m):
    uid = m.from_user.id
    if not users.find_one({'user_id': uid}):
        users.insert_one({'user_id': uid, 'balance': 0, 'refer': None})
    member = bot.get_chat_member(CHANNEL, uid)
    if member.status in ['member', 'administrator', 'creator']:
        show_menu(uid)
    else:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Join Done", callback_data='check_join'))
        bot.send_message(uid, f"🔔 প্রথমে আমাদের চ্যানেল Join করুন:\n{CHANNEL}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == 'check_join')
def check_join_cb(c):
    member = bot.get_chat_member(CHANNEL, c.from_user.id)
    if member.status in ['member', 'administrator', 'creator']:
        bot.delete_message(c.message.chat.id, c.message.message_id)
        show_menu(c.from_user.id)
    else:
        bot.answer_callback_query(c.id, "❌ এখনও চ্যানেল Join করেননি!")

def show_menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎯 Task", "💰 Balance")
    kb.add("👥 Refer", "📤 Withdraw")
    kb.add("📞 Support", "📸 Payment Proof")
    bot.send_message(uid, "স্বাগতম! একটি অপশন বেছে নিন:", reply_markup=kb)

# === BALANCE ===
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def check_balance(m):
    u = users.find_one({'user_id': m.from_user.id})
    bot.send_message(m.chat.id, f"💰 আপনার ব্যালেন্স: {u['balance']} কয়েন")

# === TASK SYSTEM ===
@bot.message_handler(func=lambda m: m.text == "🎯 Task")
def task_menu(m):
    kb = types.InlineKeyboardMarkup()
    for ad in ads.find({'active': True}):
        kb.add(types.InlineKeyboardButton(f"▶️ Watch Ad +{ad['reward']}", callback_data=f"watch_{ad['_id']}"))
    bot.send_message(m.chat.id, "🪙 ৩০ সেকেন্ড এড দেখে কয়েন আয় করুন:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('watch_'))
def watch_ad(c):
    ad_id = c.data.split('_')[1]
    ad = ads.find_one({'_id': ad_id})
    if not ad:
        return bot.answer_callback_query(c.id, "❌ এই এড আর সক্রিয় নেই।")
    bot.send_message(c.from_user.id, f"▶️ এই লিংকে ৩০ সেকেন্ড থাকুন:\n{ad['link']}")
    task_logs.insert_one({
        'user_id': c.from_user.id,
        'start': datetime.utcnow(),
        'ad_id': ad_id,
        'reward': ad['reward'],
        'claimed': False
    })
    time.sleep(2)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ I watched full", callback_data="claim"))
    bot.send_message(c.from_user.id, "৩০ সেকেন্ড শেষ হলে নিচের বাটনে ক্লিক করুন:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == 'claim')
def claim_reward(c):
    log = task_logs.find_one({'user_id': c.from_user.id, 'claimed': False})
    if not log:
        return bot.answer_callback_query(c.id, "❌ আপনি কোনো Task করছেন না!")
    elapsed = (datetime.utcnow() - log['start']).total_seconds()
    if elapsed >= 30:
        users.update_one({'user_id': c.from_user.id}, {'$inc': {'balance': log['reward']}})
        task_logs.update_one({'_id': log['_id']}, {'$set': {'claimed': True}})
        bot.send_message(c.from_user.id, f"✅ আপনি পেয়েছেন {log['reward']} কয়েন!")
    else:
        bot.answer_callback_query(c.id, f"⏱️ {int(elapsed)} সেকেন্ড হয়েছে, আরও সময় থাকুন!")

# === PLACEHOLDER MENU ===
@bot.message_handler(func=lambda m: m.text in ["👥 Refer", "📤 Withdraw", "📞 Support", "📸 Payment Proof"])
def placeholders(m):
    bot.send_message(m.chat.id, "🔜 এই ফিচারটি শীঘ্রই আসছে!")

# === ADMIN PANEL ===
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if m.from_user.id != ADMIN_ID: return
    text = (
        "🛠️ Admin Panel Commands:\n"
        "/users - Total users\n"
        "/addcoins user_id amount\n"
        "/balance user_id\n"
        "/broadcast message\n"
        "/addtask link reward"
    )
    bot.send_message(m.chat.id, text)

@bot.message_handler(commands=['addtask'])
def add_task(m):
    if m.from_user.id != ADMIN_ID: return
    try:
        _, link, reward = m.text.split()
        ad = {'link': link, 'reward': int(reward), 'active': True}
        ads.insert_one(ad)
        bot.send_message(m.chat.id, "✅ Task যোগ হয়েছে!")
    except:
        bot.send_message(m.chat.id, "❌ ফরম্যাট: /addtask link reward")

@bot.message_handler(commands=['users'])
def total_users(m):
    if m.from_user.id != ADMIN_ID: return
    count = users.count_documents({})
    bot.send_message(m.chat.id, f"👥 মোট ইউজার: {count}")

@bot.message_handler(commands=['addcoins'])
def add_coins(m):
    if m.from_user.id != ADMIN_ID: return
    try:
        _, uid, amt = m.text.split()
        uid = int(uid)
        amt = int(amt)
        users.update_one({'user_id': uid}, {'$inc': {'balance': amt}})
        bot.send_message(m.chat.id, f"✅ {uid} ইউজারকে {amt} কয়েন দেওয়া হয়েছে")
    except:
        bot.send_message(m.chat.id, "❌ ফরম্যাট: /addcoins user_id amount")

@bot.message_handler(commands=['balance'])
def check_user_balance(m):
    if m.from_user.id != ADMIN_ID: return
    try:
        _, uid = m.text.split()
        uid = int(uid)
        user = users.find_one({'user_id': uid})
        if user:
            bot.send_message(m.chat.id, f"💰 {uid} এর ব্যালেন্স: {user['balance']} কয়েন")
        else:
            bot.send_message(m.chat.id, "❌ ইউজার পাওয়া যায়নি")
    except:
        bot.send_message(m.chat.id, "❌ ফরম্যাট: /balance user_id")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(m):
    if m.from_user.id != ADMIN_ID: return
    msg = m.text.replace("/broadcast ", "")
    sent = 0
    for u in users.find():
        try:
            bot.send_message(u['user_id'], msg)
            sent += 1
        except:
            continue
    bot.send_message(m.chat.id, f"✅ {sent} জনকে বার্তা পাঠানো হয়েছে")

# === RUN ===
print("🤖 Bot is running...")
bot.infinity_polling()
