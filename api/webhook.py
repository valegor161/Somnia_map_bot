import json
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from flask import Flask, request
from telegram import Update
import main as bot_main
from database import init_db

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
app = Flask(__name__)
_bot_app = None


async def _get_bot_app():
    global _bot_app
    if _bot_app is None:
        init_db()
        _bot_app = bot_main.build_application(TOKEN)
        await _bot_app.initialize()
    return _bot_app


async def _process(data: dict):
    bot_app = await _get_bot_app()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    try:
        asyncio.run(_process(data))
    except Exception as e:
        print(f"Error: {e}")
    return "OK", 200


@app.route("/")
def index():
    return "Бот 'Карта сновидений' работает!", 200


@app.route("/health")
def health():
    return "OK", 200
