import json
import asyncio
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
import main as bot_main
from database import init_db

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
_app = None


async def _get_app() -> Application:
    global _app
    if _app is None:
        init_db()
        _app = bot_main.build_application(TOKEN)
        await _app.initialize()
    return _app


async def _process(data: dict):
    app = await _get_app()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            asyncio.run(_process(data))
        except Exception as e:
            print(f"Error: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Бот 'Карта сновидений' работает!".encode("utf-8"))

    def log_message(self, format, *args):
        pass
