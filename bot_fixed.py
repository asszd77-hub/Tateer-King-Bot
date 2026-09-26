# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import aiohttp
import json
import random
import telebot
from telebot import types
from datetime import datetime, timedelta
import pytz
import time
from threading import Thread

# ====================================================================
# 1. الإعدادات والبيانات
# ====================================================================

BOT_TOKEN = "8918540263:AAFtZKNYqVAgcdY0HEVmyrZPhym3_NJKe2E"
ADMIN_ID = 1906886647 
CHANNEL_USERNAME = "@dollar7788" 
CHANNEL_URL = "https://t.me/dollar7788"
EGYPT_TZ = pytz.timezone("Africa/Cairo")

USERS_FILE = "bot_users.json"
CONFIG_FILE = "bot_config.json"
PENDING_REQUESTS_FILE = "pending_requests.json"

SUBSCRIPTION_PLANS = {
    "1": {"name": "اشتراك يوم", "price": 15, "days": 1},
    "2": {"name": "اشتراك 10 أيام", "price": 80, "days": 10},
    "3": {"name": "اشتراك شهر", "price": 150, "days": 30},
}

def load_data():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def load_pending_requests():
    if os.path.exists(PENDING_REQUESTS_FILE):
        try:
            with open(PENDING_REQUESTS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_pending_requests(requests):
    with open(PENDING_REQUESTS_FILE, "w", encoding="utf-8") as f: json.dump(requests, f, ensure_ascii=False, indent=2)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {"is_free": False, "total_ops": 0}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(config, f, ensure_ascii=False, indent=2)

USERS = load_data()
CONFIG = load_config()
PENDING_REQUESTS = load_pending_requests()
bot = telebot.TeleBot(BOT_TOKEN)
ACTIVE_OPERATIONS = {}

# ====================================================================
# 2. التحقق والاشتراك
# ====================================================================

def check_channel_sub(user_id):
    if user_id == ADMIN_ID: return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]: return True
    except: pass
    return False

def subscription_required(func):
    def wrapper(message):
        if not check_channel_sub(message.from_user.id):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 انضم للقناة من هنا", url=CHANNEL_URL))
            markup.add(types.InlineKeyboardButton("✅ تم الانضمام", callback_data="check_sub"))
            bot.send_message(message.chat.id, f"⚠️ يجب عليك الانضمام لقناة البوت أولاً لاستخدامه!\nرابط القناة: {CHANNEL_URL}", reply_markup=markup)
            return
        return func(message)
    return wrapper

def get_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛑 إلغاء العملية")
    return markup

def is_paid_user(user_id):
    if user_id == ADMIN_ID or CONFIG["is_free"]: return True
    user = USERS.get(str(user_id))
    if not user or "expire_date" not in user: return False
    expire_date = datetime.fromisoformat(user["expire_date"])
    return datetime.now(EGYPT_TZ) < expire_date

# ====================================================================
# 3. منطق Tateer Original King V4 (أقصى سرعة تزامن)
# ====================================================================

CLIENT_SECRET = "95fd95fb-7489-4958-8ae6-d31a525cd20a"
CLIENT_ID = "ana-vodafone-app"

def get_headers(msisdn, is_web=True):
    # التأكد من استخدام الرقم بالتنسيق المطلوب في الـ headers
    clean_msisdn = msisdn if msisdn.startswith("0") else "0" + msisdn.replace("201", "01").replace("20", "")
    if is_web:
        return {"msisdn": clean_msisdn, "Accept": "application/json", "Content-Type": "application/json; charset=UTF-8", "User-Agent": "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0", "Origin": "https://web.vodafone.com.eg", "Referer": "https://web.vodafone.com.eg/spa/familySharing", "clientId": "WebsiteConsumer"}
    return {"msisdn": clean_msisdn, "Accept": "application/json", "Content-Type": "application/json; charset=UTF-8", "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1", "Origin": "https://mobile.vodafone.com.eg", "Referer": "https://mobile.vodafone.com.eg/spa/familySharing", "clientId": "AnaVodafoneAndroid"}

async def login_async(session, phone, password):
    url = "https://mobile.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/token"
    payload = {"grant_type": "password", "username": phone, "password": password, "client_secret": CLIENT_SECRET, "client_id": CLIENT_ID}
    headers = {"User-Agent": "okhttp/4.12.0", "clientId": "AnaVodafoneAndroid"}
    last_error = "لم يتم الاتصال بالسيرفر"
    for attempt in range(3):
        try:
            async with session.post(url, data=payload, headers=headers, timeout=25) as response:
                body = await response.text()
                print(f"[LOGIN] محاولة {attempt+1} | رقم: {phone} | status: {response.status} | رد: {body[:300]}")
                if response.status == 200:
                    data = json.loads(body)
                    token = data.get("access_token")
                    if token:
                        return token, None  # ✅ الإصلاح: دايمًا tuple
                    last_error = "✅ الاتصال نجح لكن السيرفر لم يُرسل token — ربما تغير API فودافون"
                elif response.status == 401:
                    # محاولة استخراج رسالة السيرفر
                    try:
                        err_data = json.loads(body)
                        srv_msg = err_data.get("error_description") or err_data.get("error") or body[:120]
                    except Exception:
                        srv_msg = body[:120]
                    last_error = f"❌ رقم أو باسورد غلط (401)\n📋 سيرفر: {srv_msg}"
                    break
                elif response.status == 400:
                    try:
                        err_data = json.loads(body)
                        srv_msg = err_data.get("error_description") or err_data.get("error") or body[:120]
                    except Exception:
                        srv_msg = body[:120]
                    last_error = f"❌ بيانات ناقصة أو خاطئة (400)\n📋 سيرفر: {srv_msg}"
                    break
                elif response.status == 403:
                    last_error = f"🚫 محظور من السيرفر (403) — قد يكون الحساب موقوف"
                    break
                elif response.status == 429:
                    last_error = f"⏳ كثرة المحاولات (429 Rate Limit) — انتظر وحاول لاحقاً"
                    break
                elif response.status == 500:
                    last_error = f"🔴 خطأ في سيرفر فودافون (500) — المشكلة من جهتهم"
                elif response.status == 503:
                    last_error = f"🔴 سيرفر فودافون غير متاح حالياً (503) — جرب لاحقاً"
                else:
                    last_error = f"⚠️ رد غير متوقع (status {response.status})\n📋 {body[:150]}"
        except asyncio.TimeoutError:
            last_error = f"⏱ انتهت مهلة الاتصال (25 ثانية) — السيرفر لم يرد"
            print(f"[LOGIN] Timeout محاولة {attempt+1} | رقم: {phone}")
        except aiohttp.ClientConnectorError as e:
            last_error = f"🌐 فشل الاتصال بالإنترنت: {str(e)}"
            print(f"[LOGIN] Connection Error | رقم: {phone} | {e}")
        except Exception as e:
            last_error = f"خطأ غير متوقع: {str(e)}"
            print(f"[LOGIN] Error محاولة {attempt+1} | رقم: {phone} | {e}")
        if attempt < 2:
            await asyncio.sleep(1.5)
    print(f"[LOGIN] فشل نهائي | رقم: {phone} | السبب: {last_error}")
    return None, last_error

async def invite_send_v4(session, token, owner, member, quota, is_web=True):
    url = "https://web.vodafone.com.eg/services/dxl/cg/customerGroupAPI/customerGroup" if is_web else "https://mobile.vodafone.com.eg/services/dxl/cg/customerGroupAPI/customerGroup"
    payload = {"name": "FlexFamily", "type": "SendInvitation", "category": [{"value": "523", "listHierarchyId": "PackageID"}, {"value": "47", "listHierarchyId": "TemplateID"}, {"value": "523", "listHierarchyId": "TierID"}, {"value": "percentage", "listHierarchyId": "familybehavior"}], "parts": {"member": [{"id": [{"value": owner, "schemeName": "MSISDN"}], "type": "Owner"}, {"id": [{"value": member, "schemeName": "MSISDN"}], "type": "Member"}], "characteristicsValue": {"characteristicsValue": [{"characteristicName": "quotaDist1", "value": str(quota), "type": "percentage"}]}}}
    headers = get_headers(owner, is_web)
    headers["Authorization"] = f"Bearer {token}"
    source = "🌐web" if is_web else "📱mob"
    try:
        async with session.post(url, json=payload, headers=headers, timeout=30) as r:
            text = await r.text()
            print(f"[INVITE] {source} | status: {r.status} | رد: {text[:200]}")
            if r.status in [200, 201, 204]:
                return True, f"{source} ✅ ({r.status})"
            # استخراج رسالة السيرفر بشكل واضح
            try:
                err_data = json.loads(text)
                srv_msg = (err_data.get("message") or err_data.get("error_description")
                           or err_data.get("error") or err_data.get("description") or text[:200])
            except Exception:
                srv_msg = text[:200]
            # ترجمة أكواد الأخطاء الشائعة
            if r.status == 401:
                reason = f"{source} 🔑 Token منتهي أو غير صالح (401)"
            elif r.status == 403:
                reason = f"{source} 🚫 مرفوض (403) — الرقم محظور أو ليس عليه خطة مناسبة"
            elif r.status == 404:
                reason = f"{source} 🔍 الخدمة غير موجودة (404) — قد يكون الـ API تغير"
            elif r.status == 409:
                reason = f"{source} 🔄 دعوة موجودة مسبقاً (409) — يجب الإلغاء أولاً"
            elif r.status == 422:
                reason = f"{source} ⚠️ بيانات غير مقبولة (422)"
            elif r.status == 429:
                reason = f"{source} ⏳ Rate Limit (429) — فودافون قفلت الطلبات مؤقتاً"
            elif r.status == 500:
                reason = f"{source} 🔴 خطأ سيرفر فودافون (500)"
            elif r.status == 503:
                reason = f"{source} 🔴 السيرفر غير متاح (503)"
            else:
                reason = f"{source} ❓ status {r.status}"
            return False, f"{reason}\n📋 رد السيرفر: {srv_msg[:150]}"
    except asyncio.TimeoutError:
        return False, f"{source} ⏱ Timeout (30 ثانية) — السيرفر لم يرد"
    except aiohttp.ClientConnectorError as e:
        return False, f"{source} 🌐 خطأ اتصال: {str(e)}"
    except Exception as e:
        print(f"[INVITE ERROR] {source} {e}")
        return False, f"{source} خطأ: {str(e)}"

async def remove_member_async(session, token, owner, member):
    # التنسيق الدولي الصريح
    o_num = owner if owner.startswith("2") else "2" + owner
    m_num = member if member.startswith("2") else "2" + member
    
    # محاولة الحذف باستخدام الـ Payload التقليدي وإلغاء الدعوة
    payload_remove = {
        "category": [{"listHierarchyId": "TemplateID", "value": "47"}],
        "parts": {
            "member": [
                {"id": [{"schemeName": "MSISDN", "value": o_num}], "type": "Owner"},
                {"id": [{"schemeName": "MSISDN", "value": m_num}], "type": "Member"}
            ]
        },
        "type": "FamilyRemoveMember"
    }
    
    payload_cancel = {
        "category": [{"listHierarchyId": "TemplateID", "value": "47"}],
        "parts": {
            "member": [
                {"id": [{"schemeName": "MSISDN", "value": o_num}], "type": "Owner"},
                {"id": [{"schemeName": "MSISDN", "value": m_num}], "type": "Member"}
            ]
        },
        "type": "CancelInvitation"
    }
    
    headers = get_headers(owner, True)
    headers["Authorization"] = f"Bearer {token}"
    
    # قائمة الروابط والطرق لتجربتها بالترتيب
    attempts = [
        # 1. محاولة إلغاء الدعوة أولاً (POST) - هذا هو الحل لمشكلة الدعوة المعلقة
        ("POST", "https://web.vodafone.com.eg/services/dxl/cg/customerGroupAPI/customerGroup", payload_cancel),
        # 2. الرابط القياسي (DELETE)
        ("DELETE", "https://web.vodafone.com.eg/services/dxl/cg/customerGroupAPI/customerGroup", payload_remove),
        # 3. الرابط القياسي (POST)
        ("POST", "https://web.vodafone.com.eg/services/dxl/cg/customerGroupAPI/customerGroup", payload_remove),
        # 4. رابط إدارة العائلة البديل (DELETE)
        ("DELETE", "https://web.vodafone.com.eg/services/dxl/cg/manageFamilyAPI/manageFamily", payload_remove),
        # 5. رابط إدارة العائلة البديل (POST)
        ("POST", "https://web.vodafone.com.eg/services/dxl/cg/manageFamilyAPI/manageFamily", payload_remove)
    ]
    
    all_resps = []
    try:
        for method, url, p in attempts:
            try:
                if method == "DELETE":
                    async with session.delete(url, headers=headers, json=p, timeout=15) as r:
                        txt = await r.text()
                        if r.status in [200, 201, 204]: return True, txt
                        all_resps.append(f"{method} {url.split("/")[-1]}: {r.status}")
                else:
                    async with session.post(url, headers=headers, json=p, timeout=15) as r:
                        txt = await r.text()
                        if r.status in [200, 201, 204]: return True, txt
                        all_resps.append(f"{method} {url.split("/")[-1]}: {r.status}")
            except: continue
            
        return False, " | ".join(all_resps) if all_resps else "All routes failed"
                
    except Exception as e:
        return False, str(e)

async def accept_invitation_async(session, token, owner, member):
    url = "https://web.vodafone.com.eg/services/dxl/cg/customerGroupAPI/customerGroup"
    payload = {"category": [{"listHierarchyId": "TemplateID", "value": "47"}], "name": "FlexFamily", "parts": {"member": [{"id": [{"schemeName": "MSISDN", "value": owner}], "type": "Owner"}, {"id": [{"schemeName": "MSISDN", "value": member}], "type": "Member"}]}, "type": "AcceptInvitation"}
    headers = get_headers(member, True); headers["Authorization"] = f"Bearer {token}"
    try:
        async with session.patch(url, headers=headers, json=payload, timeout=20) as r: 
            return r.status in [200, 201, 204]
    except: return False

# ====================================================================
# 4. تدفق العملية
# ====================================================================

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 بدء عملية جديدة")
    markup.add("👤 حسابي", "💳 تجديد الاشتراك")
    if user_id == ADMIN_ID: markup.add("⚙️ لوحة الإدارة")
    return markup

@bot.message_handler(func=lambda m: m.text == "🛑 إلغاء العملية")
def cancel_global(message):
    user_id = message.from_user.id
    ACTIVE_OPERATIONS.pop(user_id, None)
    bot.clear_step_handler_by_chat_id(message.chat.id)
    bot.send_message(message.chat.id, "🛑 تم إلغاء العملية والعودة للقائمة الرئيسية.", reply_markup=get_main_keyboard(user_id))

@bot.message_handler(commands=["start"])
def start(message):
    user_id = str(message.from_user.id)
    is_new = user_id not in USERS
    if is_new:
        USERS[user_id] = {
            "joined": datetime.now(EGYPT_TZ).isoformat(),
            "expire_date": datetime.now(EGYPT_TZ).isoformat(),
            "first_name": message.from_user.first_name or "",
            "username": message.from_user.username or ""
        }
        save_data(USERS)
        try:
            uname = f"@{message.from_user.username}" if message.from_user.username else "بدون يوزر"
            fname = message.from_user.first_name or "بدون اسم"
            bot.send_message(
                ADMIN_ID,
                f"🔔 *مستخدم جديد انضم للبوت!*\n\n"
                f"👤 الاسم: {fname}\n"
                f"🔗 اليوزر: {uname}\n"
                f"🆔 ID: `{user_id}`\n"
                f"📅 التاريخ: {datetime.now(EGYPT_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"👥 إجمالي المستخدمين: {len(USERS)}",
                parse_mode="Markdown"
            )
            print(f"[NEW USER] {fname} | {uname} | {user_id}")
        except Exception as e:
            print(f"[NEW USER NOTIFY ERROR] {e}")

    bot.send_message(
        message.chat.id,
        f"👋 *أهلاً بك في Tateer Original King!*\n\n"
        f"📢 قناة البوت: {CHANNEL_URL}",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

@bot.message_handler(func=lambda m: m.text == "🚀 بدء عملية جديدة")
@subscription_required
def start_op(message):
    if not is_paid_user(message.from_user.id):
        bot.send_message(message.chat.id, "⚠️ عذراً، يجب أن يكون لديك اشتراك مفعل لاستخدام البوت.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("✅قبول تلقائي", "⭕تعليق دعوتين")
    markup.add("🛑 إلغاء العملية")
    bot.send_message(message.chat.id, "🔄 اختر نوع العملية أولاً:", reply_markup=markup)
    bot.register_next_step_handler(message, get_owner_num)

def get_owner_num(message):
    if message.text == "🛑 إلغاء العملية": return cancel_global(message)
    op_type = message.text.strip()
    if op_type not in ["✅قبول تلقائي", "⭕تعليق دعوتين"]:
        bot.send_message(message.chat.id, "❌ اختيار غير صحيح.")
        return
    bot.send_message(message.chat.id, "📱 أدخل رقم الأونر (المالك):", reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, get_owner_pass, op_type)

def get_owner_pass(message, op_type):
    if message.text == "🛑 إلغاء العملية": return cancel_global(message)
    owner_num = message.text.strip()
    bot.send_message(message.chat.id, "🔒 أدخل باسورد الأونر:", reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, get_member_num, op_type, owner_num)

def get_member_num(message, op_type, owner_num):
    if message.text == "🛑 إلغاء العملية": return cancel_global(message)
    owner_pass = message.text.strip()
    bot.send_message(message.chat.id, "👥 أدخل رقم الفرد:", reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, get_member_pass, op_type, owner_num, owner_pass)

def get_member_pass(message, op_type, owner_num, owner_pass):
    if message.text == "🛑 إلغاء العملية": return cancel_global(message)
    member_num = message.text.strip()
    bot.send_message(message.chat.id, "🔑 أدخل باسورد الفرد:", reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, get_quota, op_type, owner_num, owner_pass, member_num)

def get_quota(message, op_type, owner_num, owner_pass, member_num):
    if message.text == "🛑 إلغاء العملية": return cancel_global(message)
    member_pass = message.text.strip()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("10", "20", "40")
    markup.add("🛑 إلغاء العملية")
    bot.send_message(message.chat.id, "📊 اختر النسبة (10, 20, 40):", reply_markup=markup)
    bot.register_next_step_handler(message, run_operation, op_type, owner_num, owner_pass, member_num, member_pass)

def run_operation(message, op_type, owner_num, owner_pass, member_num, member_pass):
    if message.text == "🛑 إلغاء العملية": return cancel_global(message)
    quota = message.text.strip()
    Thread(target=lambda: asyncio.run(run_op_async(message.chat.id, message.from_user.id, owner_num, owner_pass, member_num, member_pass, quota, op_type))).start()

# ====================================================================
# 5. تنفيذ العملية (المنطق المثالي والمطلوب حرفياً)
# ====================================================================

async def run_op_async(chat_id, user_id, owner_num, owner_pass, member_num, member_pass, quota, op_type):
    ACTIVE_OPERATIONS[user_id] = True
    bot.send_message(chat_id, "⏳ جاري البدء بأقصى سرعة إرسال...", reply_markup=get_main_keyboard(user_id))
    
    cancel_markup = types.InlineKeyboardMarkup()
    cancel_markup.add(types.InlineKeyboardButton("🛑 إلغاء العملية", callback_data="cancel_op"))
    msg = bot.send_message(chat_id, "🔑 جاري تسجيل الدخول...", reply_markup=cancel_markup)
    
    # استخدام TCPConnector لسرعة قصوى مع تعطيل الـ SSL Verification لتقليل وقت الاستجابة
    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300, ssl=False, limit_per_host=4)
    async with aiohttp.ClientSession(connector=connector) as session:
        login_tasks = [login_async(session, owner_num, owner_pass), login_async(session, member_num, member_pass)]
        results_login = await asyncio.gather(*login_tasks)

        # login_async ترجع token مباشرة لو نجحت، أو (None, error) لو فشلت
        def parse_login(res):
            if isinstance(res, tuple):
                return res[0], res[1]
            return res, None

        o_token, o_err = parse_login(results_login[0])
        m_token, m_err = parse_login(results_login[1])

        if not o_token or not m_token:
            o_status = "✅ نجح" if o_token else f"❌ فشل\n    ↳ {o_err or 'خطأ غير معروف'}"
            m_status = "✅ نجح" if m_token else f"❌ فشل\n    ↳ {m_err or 'خطأ غير معروف'}"
            fail_msg = (
                "❌ *فشل تسجيل الدخول!*\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"👑 *الأونر* ({owner_num}):\n{o_status}\n\n"
                f"👤 *الفرد* ({member_num}):\n{m_status}\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "💡 *تحقق من:*\n"
                "• صحة الأرقام والباسوردات\n"
                "• أن الحساب غير موقوف\n"
                "• اتصال الإنترنت بالسيرفر"
            )
            bot.edit_message_text(fail_msg, chat_id, msg.message_id, parse_mode="Markdown")
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"⚠️ *فشل تسجيل دخول*\n"
                    f"👤 مستخدم: `{user_id}`\n"
                    f"👑 أونر: `{owner_num}`\n↳ {o_err or 'OK'}\n"
                    f"👤 فرد: `{member_num}`\n↳ {m_err or 'OK'}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            ACTIVE_OPERATIONS.pop(user_id, None)
            return

        bot.edit_message_text("✅ تم تسجيل الدخول بنجاح! جاري بدء العملية...", chat_id, msg.message_id, reply_markup=cancel_markup)

        success_count = 0
        last_resp = ""
        all_fail_reasons = []  # لتجميع أسباب الفشل عبر المحاولات

        for i in range(1, 11):
            if user_id not in ACTIVE_OPERATIONS:
                bot.edit_message_text("🛑 تم إلغاء العملية.", chat_id, msg.message_id); return

            bot.edit_message_text(
                f"🚀 *ضرب رباعي — محاولة {i}/10*\n⏳ جاري الإرسال...",
                chat_id, msg.message_id,
                reply_markup=cancel_markup,
                parse_mode="Markdown"
            )

            # إرسال متدرج بدل إرسال كل الطلبات في نفس اللحظة
            async def send_with_delay(is_web, delay):
                await asyncio.sleep(delay)
                return await invite_send_v4(session, o_token, owner_num, member_num, quota, is_web)

            tasks = [
                send_with_delay(True,  0.0),   # web  فوري
                send_with_delay(False, 0.3),   # mob  بعد 300ms
                send_with_delay(True,  0.6),   # web  بعد 600ms
                send_with_delay(False, 0.9),   # mob  بعد 900ms
            ]
            results = await asyncio.gather(*tasks)

            success_count = sum(1 for s, _ in results if s)
            fail_details = [detail for s, detail in results if not s]

            if success_count >= 2:
                break

            if success_count == 1:
                bot.edit_message_text(
                    f"⚠️ *نجحت دعوة واحدة فقط (محاولة {i})*\n"
                    f"⏳ انتظار 30 ثانية قبل الإلغاء وإعادة المحاولة...",
                    chat_id, msg.message_id,
                    reply_markup=cancel_markup,
                    parse_mode="Markdown"
                )
                await asyncio.sleep(30)
                if user_id not in ACTIVE_OPERATIONS: return

                bot.edit_message_text("🔄 جاري إلغاء الدعوة الواحدة...", chat_id, msg.message_id, reply_markup=cancel_markup)
                success_cancel, cancel_resp = await remove_member_async(session, o_token, owner_num, member_num)
                if success_cancel:
                    bot.edit_message_text(
                        f"✅ تم إلغاء الدعوة. إعادة المحاولة خلال 5 ثوانٍ...",
                        chat_id, msg.message_id,
                        reply_markup=cancel_markup
                    )
                    await asyncio.sleep(5)
                else:
                    bot.edit_message_text(
                        f"❌ *فشل إلغاء الدعوة الواحدة*\n"
                        f"📋 السبب: {cancel_resp[:150]}\n"
                        f"🛑 تم إيقاف العملية لضمان السلامة.",
                        chat_id, msg.message_id,
                        parse_mode="Markdown"
                    )
                    ACTIVE_OPERATIONS.pop(user_id, None)
                    return
            else:
                # لم تنجح أي دعوة — نعرض أسباب الفشل بالتفصيل
                last_resp = fail_details[0] if fail_details else "لا يوجد رد"
                all_fail_reasons = fail_details

                # كشف Rate Limit في أي من الردود
                combined = " ".join(fail_details).lower()
                is_rate_limit = "rate limit" in combined or "429" in combined or "⏳" in combined

                fail_summary = "\n".join(f"  {d}" for d in fail_details[:4]) if fail_details else "لا يوجد تفاصيل"
                status_msg = (
                    f"❌ *فشل المحاولة {i}/10*\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 نجح: {success_count}/4 طلبات\n"
                    f"📋 *تفاصيل الفشل:*\n{fail_summary}\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                )
                if is_rate_limit:
                    wait = 20 if i <= 3 else 35
                    status_msg += f"⏳ Rate Limit مكتشف — انتظار {wait} ثانية تلقائياً..."
                    bot.edit_message_text(status_msg, chat_id, msg.message_id, reply_markup=cancel_markup, parse_mode="Markdown")
                    await asyncio.sleep(wait)
                else:
                    status_msg += f"🔄 إعادة المحاولة خلال 4 ثوانٍ..."
                    bot.edit_message_text(status_msg, chat_id, msg.message_id, reply_markup=cancel_markup, parse_mode="Markdown")
                    await asyncio.sleep(4)

        if success_count < 2:
            fail_summary = "\n".join(f"• {d}" for d in all_fail_reasons[:4]) if all_fail_reasons else last_resp[:200]
            final_fail_msg = (
                f"❌ *فشل بعد 10 محاولات*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📋 *آخر أسباب الفشل:*\n{fail_summary}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💡 *المقترح:* تحقق من الأسباب أعلاه وأرسلها للدعم."
            )
            bot.edit_message_text(final_fail_msg, chat_id, msg.message_id, parse_mode="Markdown")
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"❌ *فشل عملية كاملة*\n"
                    f"👤 مستخدم: `{user_id}`\n"
                    f"👑 أونر: `{owner_num}`\n"
                    f"👤 فرد: `{member_num}`\n"
                    f"📋 السبب:\n{fail_summary}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            ACTIVE_OPERATIONS.pop(user_id, None); return

        if op_type == "⭕تعليق دعوتين":
            bot.edit_message_text(
                f"✅ *نجح التعليق!* 🎯\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📊 دعوات ناجحة: {success_count}/4\n"
                f"👑 الأونر: `{owner_num}`\n"
                f"👤 الفرد: `{member_num}`",
                chat_id, msg.message_id,
                parse_mode="Markdown"
            )
            CONFIG["total_ops"] += 1; save_config(CONFIG)
            ACTIVE_OPERATIONS.pop(user_id, None); return

        bot.edit_message_text(
            f"✅ *تم إرسال {success_count} دعوات بنجاح!*\n"
            f"⏳ انتظار 5 دقائق قبل القبول التلقائي...\n"
            f"_(اضغط إلغاء إذا أردت إيقاف العملية)_",
            chat_id, msg.message_id,
            reply_markup=cancel_markup,
            parse_mode="Markdown"
        )
        await asyncio.sleep(300)

        if user_id not in ACTIVE_OPERATIONS:
            bot.edit_message_text("🛑 تم الإلغاء قبل القبول.", chat_id, msg.message_id); return

        bot.edit_message_text("🔄 جاري القبول التلقائي...", chat_id, msg.message_id, reply_markup=cancel_markup)
        accept_ok = await accept_invitation_async(session, m_token, owner_num, member_num)
        if accept_ok:
            bot.edit_message_text(
                f"🎉 *تمت العملية بنجاح كامل!*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"✅ الإرسال: {success_count}/4 دعوات\n"
                f"✅ القبول: تم تلقائياً\n"
                f"👑 الأونر: `{owner_num}`\n"
                f"👤 الفرد: `{member_num}`\n"
                f"📊 النسبة: {quota}%",
                chat_id, msg.message_id,
                parse_mode="Markdown"
            )
            CONFIG["total_ops"] += 1; save_config(CONFIG)
        else:
            bot.edit_message_text(
                f"⚠️ *تم الإرسال لكن فشل القبول التلقائي!*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"✅ الإرسال: {success_count}/4 دعوات — نجح\n"
                f"❌ القبول: فشل\n\n"
                f"💡 *المقترح:* اقبل الدعوة يدوياً من تطبيق فودافون.",
                chat_id, msg.message_id,
                parse_mode="Markdown"
            )
            
    ACTIVE_OPERATIONS.pop(user_id, None)

# ====================================================================
# 6. إدارة طلبات الاشتراك
# ====================================================================

def process_payment_number(message, plan_key):
    user_id = str(message.from_user.id)
    payment_number = message.text.strip()
    request = {
        "id": random.randint(1000, 9999),
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "plan": plan_key,
        "sender_num": payment_number,
        "time": datetime.now(EGYPT_TZ).isoformat()
    }
    PENDING_REQUESTS.append(request)
    save_pending_requests(PENDING_REQUESTS)
    bot.send_message(message.chat.id, "✅ تم استلام طلبك، سيتم تفعيل الاشتراك فور التأكد من التحويل.")
    bot.send_message(ADMIN_ID, f"🔔 طلب اشتراك جديد من {message.from_user.id} ({payment_number})")

def display_pending_requests(message):
    if not PENDING_REQUESTS:
        bot.send_message(message.chat.id, "📭 لا توجد طلبات معلقة.")
        return
    for req in PENDING_REQUESTS:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_request_{req['id']}"),
            types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_request_{req['id']}")
        )
        plan = SUBSCRIPTION_PLANS.get(req['plan'], {})
        bot.send_message(message.chat.id, f"👤 المستخدم: {req['user_id']}\n📱 رقم المحول: {req['sender_num']}\n📦 الخطة: {plan.get('name')}", reply_markup=markup)

def approve_subscription_request(message, request_id):
    global PENDING_REQUESTS
    req = next((r for r in PENDING_REQUESTS if r['id'] == request_id), None)
    if not req: return
    
    user_id = str(req['user_id'])
    plan = SUBSCRIPTION_PLANS.get(req['plan'])
    
    if user_id not in USERS: USERS[user_id] = {"joined": datetime.now(EGYPT_TZ).isoformat()}
    
    current_expire = datetime.now(EGYPT_TZ)
    if "expire_date" in USERS[user_id]:
        old_expire = datetime.fromisoformat(USERS[user_id]["expire_date"])
        if old_expire > current_expire: current_expire = old_expire
        
    new_expire = current_expire + timedelta(days=plan['days'])
    USERS[user_id]["expire_date"] = new_expire.isoformat()
    save_data(USERS)
    
    PENDING_REQUESTS = [r for r in PENDING_REQUESTS if r['id'] != request_id]
    save_pending_requests(PENDING_REQUESTS)
    
    bot.send_message(message.chat.id, f"✅ تم تفعيل الاشتراك للمستخدم {user_id}")
    try: bot.send_message(int(user_id), f"🎉 مبروك! تم تفعيل اشتراكك ({plan['name']}) بنجاح.")
    except: pass

def reject_subscription_request(message, request_id):
    global PENDING_REQUESTS
    req = next((r for r in PENDING_REQUESTS if r['id'] == request_id), None)
    if not req: return
    
    PENDING_REQUESTS = [r for r in PENDING_REQUESTS if r['id'] != request_id]
    save_pending_requests(PENDING_REQUESTS)
    bot.send_message(message.chat.id, "❌ تم رفض الطلب.")

def add_sub_manual(message):
    try:
        parts = message.text.split()
        user_id = parts[0]
        days = int(parts[1])
        if user_id not in USERS: USERS[user_id] = {"joined": datetime.now(EGYPT_TZ).isoformat()}
        
        current_expire = datetime.now(EGYPT_TZ)
        if "expire_date" in USERS[user_id]:
            old_expire = datetime.fromisoformat(USERS[user_id]["expire_date"])
            if old_expire > current_expire: current_expire = old_expire
            
        new_expire = current_expire + timedelta(days=days)
        USERS[user_id]["expire_date"] = new_expire.isoformat()
        save_data(USERS)
        bot.send_message(message.chat.id, f"✅ تم إضافة {days} يوم للمستخدم {user_id}")
    except:
        bot.send_message(message.chat.id, "❌ خطأ في الصيغة.")

# ====================================================================
# 7. الكولباك
# ====================================================================

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    if call.data == "check_sub":
        if check_channel_sub(user_id):
            bot.answer_callback_query(call.id, "✅ شكراً لانضمامك!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        else: bot.answer_callback_query(call.id, "❌ لم تنضم للقناة بعد!", show_alert=True)
    elif call.data == "cancel_op":
        ACTIVE_OPERATIONS.pop(user_id, None)
        bot.answer_callback_query(call.id, "🛑 جاري إلغاء العملية...")
    elif call.data == "toggle_free" and user_id == ADMIN_ID:
        CONFIG["is_free"] = not CONFIG["is_free"]; save_config(CONFIG)
        admin_panel(call.message)
    elif call.data.startswith("sub_plan_"):
        plan_key = call.data.replace("sub_plan_", "")
        plan = SUBSCRIPTION_PLANS.get(plan_key)
        if plan:
            payment_msg = (
                f"✨ *لقد اخترت {plan['name']}* ✨\n\n"
                f"💰 *السعر:* `{plan['price']} جنيه`\n"
                f"💳 *رقم التحويل (اضغط للنسخ):*\n"
                f"`01026292411`\n\n"
                f"⚠️ *بعد التحويل:* يرجى إرسال الرقم الذي قمت بالتحويل منه هنا."
            )
            bot.send_message(call.message.chat.id, payment_msg, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_payment_number, plan_key)
        else:
            bot.answer_callback_query(call.id, "❌ خطأ في اختيار الخطة.", show_alert=True)
    elif call.data == "view_pending_requests" and user_id == ADMIN_ID:
        display_pending_requests(call.message)
    elif call.data.startswith("approve_request_") and user_id == ADMIN_ID:
        request_id = int(call.data.replace("approve_request_", ""))
        approve_subscription_request(call.message, request_id)
    elif call.data.startswith("reject_request_") and user_id == ADMIN_ID:
        request_id = int(call.data.replace("reject_request_", ""))
        reject_subscription_request(call.message, request_id)
    elif call.data == "add_sub" and user_id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "أرسل ID المستخدم وعدد الأيام (مثال: 123456 30):")
        bot.register_next_step_handler(call.message, add_sub_manual)

@bot.message_handler(func=lambda m: m.text == "⚙️ لوحة الإدارة" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"الوضع: {'مجاني' if CONFIG['is_free'] else 'مدفوع'}", callback_data="toggle_free"))
    markup.add(types.InlineKeyboardButton("إضافة اشتراك يدوي", callback_data="add_sub"))
    markup.add(types.InlineKeyboardButton(f"الطلبات المعلقة: {len(PENDING_REQUESTS)}", callback_data="view_pending_requests"))
    markup.add(types.InlineKeyboardButton(f"العمليات: {CONFIG['total_ops']}", callback_data="none"))
    markup.add(types.InlineKeyboardButton(f"المستخدمين: {len(USERS)}", callback_data="none"))
    bot.send_message(message.chat.id, "🛠️ لوحة تحكم المطور:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💳 تجديد الاشتراك")
def renew_sub(message):
    markup = types.InlineKeyboardMarkup()
    for key, plan in SUBSCRIPTION_PLANS.items():
        markup.add(types.InlineKeyboardButton(f"{key}️⃣ {plan['name']}: {plan['price']} جنيه", callback_data=f"sub_plan_{key}"))
    bot.send_message(message.chat.id, "💰 خطط الاشتراك المتوفرة، اختر الخطة التي تناسبك:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👤 حسابي")
def my_account(message):
    user_id = str(message.from_user.id)
    user = USERS.get(user_id)
    if not user:
        bot.send_message(message.chat.id, f"🆔 معرفك: {user_id}\n📊 الحالة: لا يوجد اشتراك")
        return
    expire_str = user.get("expire_date")
    if not expire_str:
        bot.send_message(message.chat.id, f"🆔 معرفك: {user_id}\n📊 الحالة: لا يوجد اشتراك")
        return
    expire = datetime.fromisoformat(expire_str)
    status = "✅ مفعل" if datetime.now(EGYPT_TZ) < expire else "❌ منتهي"
    remaining_days = (expire - datetime.now(EGYPT_TZ)).days if datetime.now(EGYPT_TZ) < expire else 0
    bot.send_message(message.chat.id, f"🆔 معرفك: {user_id}\n📊 الحالة: {status}\n⏳ ينتهي في: {expire.strftime('%Y-%m-%d %H:%M:%S')}\n🗓️ الأيام المتبقية: {remaining_days}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.send_message(message.chat.id, "أمر غير مفهوم. يرجى استخدام الأزرار المتاحة.", reply_markup=get_main_keyboard(message.from_user.id))

if __name__ == '__main__':
    print("=" * 50)
    print("🤖 Tateer Original King Bot — Started")
    print(f"📅 {datetime.now(EGYPT_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"👥 مستخدمين محملين: {len(USERS)}")
    print("=" * 50)

    # إشعار الأدمن عند تشغيل البوت
    try:
        bot.send_message(
            ADMIN_ID,
            f"✅ *البوت شغال الآن!*\n"
            f"📅 {datetime.now(EGYPT_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👥 مستخدمين: {len(USERS)}",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[STARTUP NOTIFY ERROR] {e}")

    # ✅ حذف أي webhook قديم قبل البدء بـ polling (لحل مشكلة 409)
    try:
        bot.delete_webhook()
        print("✅ تم حذف webhook القديم بنجاح")
    except Exception as e:
        print(f"⚠️ تنبيه عند حذف webhook: {e}")

    retry_delay = 15
    while True:
        try:
            print("[POLLING] جاري الاستماع للرسائل...")
            bot.infinity_polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"[POLLING ERROR] {e}")
            try:
                bot.send_message(ADMIN_ID, f"⚠️ خطأ في البولينج:\n{str(e)[:200]}\n\n🔄 إعادة التشغيل خلال {retry_delay} ثانية...")
            except Exception:
                pass
            time.sleep(retry_delay)
