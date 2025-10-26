#!/usr/bin/env python3
import os
import logging
from datetime import datetime
import requests
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()
TELEGRAM_TOKEN=os.getenv("TELEGRAM_TOKEN")
OWM_API_KEY=os.getenv("OWM_API_KEY")

if not TELEGRAM_TOKEN or not OWM_API_KEY:
    raise RuntimeError("Iltimos .env faylga TELEGRAM_TOKEN va OWM_API_KEY qo'ying")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def format_weather(data: dict) -> str:
    # extract
    name = data.get("name", "Noma'lum joy")
    sys = data.get("sys", {})
    weather = (data.get("weather") or [{}])[0]
    main = data.get("main", {})
    wind = data.get("wind", {})
    tz = data.get("timezone", 0)  # seconds offset from UTC

    desc = weather.get("description", "").capitalize()
    temp = main.get("temp")
    feels = main.get("feels_like")
    humidity = main.get("humidity")
    pressure = main.get("pressure")
    wind_speed = wind.get("speed")
    sunrise = sys.get("sunrise")
    sunset = sys.get("sunset")

    def from_ts(ts):
        if not ts: return "—"
        return datetime.utcfromtimestamp(ts + tz).strftime("%H:%M")

    sunrise_s = from_ts(sunrise)
    sunset_s = from_ts(sunset)

    emoji_map = {
        "Clear": "☀️",
        "Clouds": "☁️",
        "Rain": "🌧️",
        "Drizzle": "🌦️",
        "Thunderstorm": "⛈️",
        "Snow": "❄️",
        "Mist": "🌫️",
    }
    main_cat = weather.get("main", "")
    emoji = emoji_map.get(main_cat, "")

    lines = [
        f"📍 <b>{name}</b>",
        f"{emoji} {desc}",
        f"🌡️ Harorat: <b>{temp}°C</b> (his qilinishi: {feels}°C)",
        f"💧 Namlik: {humidity}%  |  Bosim: {pressure} hPa",
        f"💨 Shamol: {wind_speed} m/s",
        f"🌅 Quyosh chiqishi: {sunrise_s}  🌇 Quyosh botishi: {sunset_s}",
        "",
        "Ma'lumot: OpenWeatherMap API orqali."
    ]
    return "\n".join(lines)

def fetch_by_city(city: str):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OWM_API_KEY,
        "units": "metric",
        "lang": "uz"
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_by_coords(lat: float, lon: float):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OWM_API_KEY,
        "units": "metric",
        "lang": "uz"
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("Joylashuvni yuborish", request_location=True)]]
    reply = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    text = (
        "Salom! 👋\n"
        "Men ob-havo botiman. Shahar nomi orqali yoki joylashuvingizni yuborib ob-havoni bilishingiz mumkin.\n\n"
        "Foydalanish:\n"
        "• /weather <shahar> — masalan: /weather Tashkent\n"
        "• Joylashuv yuboring (location) — yaqin atrofdagi ob-havo.\n"
    )
    await update.message.reply_text(text, reply_markup=reply)

async def weather_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Iltimos shahar nomini yozing. Masalan: /weather Tashkent")
        return
    city = " ".join(args)
    msg = await update.message.reply_text(f"🔎 {city} uchun ob-havo topilyapti...")
    try:
        data = fetch_by_city(city)
        text = format_weather(data)
        await msg.edit_text(text, parse_mode="HTML")
    except requests.HTTPError as e:
        logger.exception(e)
        await msg.edit_text("Kechirasiz, shahar topilmadi yoki so'rovda xatolik yuz berdi. Iltimos to'g'ri shahar nomini yozing.")
    except Exception as e:
        logger.exception(e)
        await msg.edit_text("Xatolik yuz berdi. Keyinroq qayta urinib ko'ring.")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    if not loc:
        await update.message.reply_text("Joylashuv qabul qilinmadi.")
        return
    lat, lon = loc.latitude, loc.longitude
    msg = await update.message.reply_text("🔎 Joylashuv bo'yicha ob-havo topilyapti...")
    try:
        data = fetch_by_coords(lat, lon)
        text = format_weather(data)
        await msg.edit_text(text, parse_mode="HTML")
    except Exception as e:
        logger.exception(e)
        await msg.edit_text("Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # agar foydalanuvchi faqat shahar nomini yozsa ham ishlaydi
    city = update.message.text.strip()
    if not city:
        return
    msg = await update.message.reply_text(f"🔎 {city} uchun ob-havo topilyapti...")
    try:
        data = fetch_by_city(city)
        text = format_weather(data)
        await msg.edit_text(text, parse_mode="HTML")
    except Exception as e:
        logger.exception(e)
        await msg.edit_text("Shahar topilmadi yoki xatolik yuz berdi. /start bilan ko'rsatmalarga qarang.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather_cmd))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
