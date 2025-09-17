import os
import asyncio
import json
from typing import List
import logging
from contextlib import asynccontextmanager
from database import get_async_db

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from telegram.constants import ChatAction 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

import httpx
import crud
import models
import schemas
from database import SessionLocal, engine

from functools import lru_cache
from datetime import datetime

last_fetch = None
cached_metrics = None
CACHE_DURATION = 60  
cache_lock = asyncio.Lock()

# --- DATABASE AND APP SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- TELEGRAM BOT SETUP ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
VAULT_API_URL = "https://yield-allocator-backend-production.up.railway.app/api/vault/price/"

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command by sending a welcome message with an INLINE keyboard."""
    chat_id = update.message.chat_id
    '''db = SessionLocal()
    try:
        user_schema = schemas.UserCreate(chat_id=chat_id)
        db_user, created = crud.get_or_create_user(db, user_schema)
        if created:
            message_text = (
                "🤖 Welcome to Sentient AI!\n\n"
                "You are now subscribed. Tap the button below to get your first metrics update."
            )
        else:
            message_text = "👋 Welcome back! Tap the button for the latest metrics."
    finally:
        db.close()'''
    async with get_async_db() as db:
        user_schema = schemas.UserCreate(chat_id=chat_id)
        db_user, created = crud.get_or_create_user(db, user_schema)
        if created:
            message_text = (
                "🤖 Welcome to Sentient AI!\n\n"
                "You are now subscribed. Tap the button below to get your first metrics update."
            )
        else:
            message_text = "👋 Welcome back! Tap the button for the latest metrics."

    keyboard = [[InlineKeyboardButton("📊 Sentient Metrics", callback_data='show_metrics')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message_text, reply_markup=reply_markup)

'''
async def get_metrics_text() -> str:
    """Fetches data from the API and formats it into a string. Returns an error string on failure."""
    if cached_metrics and last_fetch and (datetime.now() - last_fetch).seconds < CACHE_DURATION:
        return cached_metrics
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(VAULT_API_URL)
            response.raise_for_status()
            vault_data = response.json()

            total_tvl = sum(float(v.get("total_assets", 0)) for v in vault_data if isinstance(v.get("total_assets"), (str, int, float)))
            tvl_formatted = f"${total_tvl:,.2f}"

            protocol_lines = []
            if total_tvl > 0:
                for vault in vault_data:
                    name = f"{vault.get('protocol', 'N/A')} {vault.get('token', 'N/A')}"
                    tvl_val = float(vault.get("total_assets", 0))
                    percent = (tvl_val / total_tvl * 100)
                    protocol_lines.append(f"• {name}: ${tvl_val:,.2f} ({percent:.1f}%)")

            return (
                "<b>📊 Sentient Metrics</b>\n\n"
                "<b>General Metrics:</b>\n"
                f"• TVL: {tvl_formatted}\n\n"
                "<b>Our Distribution:</b>\n" + "\n".join(protocol_lines)
            )
    except Exception as e:
        logger.error(f"Failed to get metrics data: {e}", exc_info=True)
        return "😕 Sorry, I couldn't fetch the metrics right now. Please try again later."
'''

'''
async def get_metrics_text() -> str:
    """Fetches data from the API and formats it into a string. Returns an error string on failure."""
    global last_fetch, cached_metrics
    async with cache_lock:
        if cached_metrics and last_fetch and (datetime.now() - last_fetch).total_seconds() < CACHE_DURATION:
            logger.info("CACHE HIT - returning cached data")
            return cached_metrics
    
    logger.info("CACHE MISS - fetching new data")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(VAULT_API_URL)
            response.raise_for_status()
            vault_data = response.json()

            total_tvl = sum(float(v.get("total_assets", 0)) for v in vault_data if isinstance(v.get("total_assets"), (str, int, float)))
            tvl_formatted = f"${total_tvl:,.2f}"

            protocol_lines = []
            if total_tvl > 0:
                for vault in vault_data:
                    name = f"{vault.get('protocol', 'N/A')} {vault.get('token', 'N/A')}"
                    tvl_val = float(vault.get("total_assets", 0))
                    percent = (tvl_val / total_tvl * 100)
                    protocol_lines.append(f"• {name}: ${tvl_val:,.2f} ({percent:.1f}%)")

            result = (
                "<b>📊 Sentient Metrics</b>\n\n"
                "<b>General Metrics:</b>\n"
                f"• TVL: {tvl_formatted}\n\n"
                "<b>Our Distribution:</b>\n" + "\n".join(protocol_lines)
            )
            
            async with cache_lock:
                cached_metrics = result
                last_fetch = datetime.now()
            
            return result
            
    except Exception as e:
        logger.error(f"Failed to get metrics data: {e}", exc_info=True)
    
        async with cache_lock:
            if cached_metrics:
                logger.info("API failed, returning stale cached data as fallback")
                return cached_metrics
    
        return "😕 Sorry, I couldn't fetch the metrics right now. Please try again later."
'''

# In your main.py file, replace the old function with this one.

async def get_metrics_text() -> str:
    """
    Fetches data from the API using a double-checked locking pattern
    to prevent race conditions.
    """
    global last_fetch, cached_metrics

    if cached_metrics and last_fetch and (datetime.now() - last_fetch).total_seconds() < CACHE_DURATION:
        logger.info("CACHE HIT - returning cached data (fast path)")
        return cached_metrics

    async with cache_lock:
        if cached_metrics and last_fetch and (datetime.now() - last_fetch).total_seconds() < CACHE_DURATION:
            logger.info("CACHE HIT - returning cached data (after waiting for lock)")
            return cached_metrics

        logger.info("CACHE MISS - fetching new data")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(VAULT_API_URL)
                response.raise_for_status()
                vault_data = response.json()

            # Format the data (your existing logic is fine)
            total_tvl = sum(float(v.get("total_assets", 0)) for v in vault_data if isinstance(v.get("total_assets"), (str, int, float)))
            tvl_formatted = f"${total_tvl:,.2f}"
            protocol_lines = []
            if total_tvl > 0:
                for vault in vault_data:
                    name = f"{vault.get('protocol', 'N/A')} {vault.get('token', 'N/A')}"
                    tvl_val = float(vault.get("total_assets", 0))
                    percent = (tvl_val / total_tvl * 100)
                    protocol_lines.append(f"• {name}: ${tvl_val:,.2f} ({percent:.1f}%)")
            
            result = (
                "<b>📊 Sentient Metrics</b>\n\n"
                "<b>General Metrics:</b>\n"
                f"• TVL: {tvl_formatted}\n\n"
                "<b>Our Distribution:</b>\n" + "\n".join(protocol_lines)
            )

            # Update the cache
            cached_metrics = result
            last_fetch = datetime.now()
            return result

        except Exception as e:
            logger.error(f"Failed to get metrics data: {e}", exc_info=True)
            # Return old data if we have it, otherwise return error
            if cached_metrics:
                logger.info("API failed, returning stale cached data as fallback")
                return cached_metrics
            return "😕 Sorry, I couldn't fetch the metrics right now. Please try again later."

async def show_metrics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the press of the INLINE button.
    It keeps the original message and sends a NEW one with the metrics and the permanent keyboard.
    """
    query = update.callback_query
    #await query.answer("Fetching...")
    await query.answer()
    #await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
    metrics_text = await get_metrics_text()

    permanent_keyboard = [[KeyboardButton("📊 Sentient Metrics")]]
    permanent_reply_markup = ReplyKeyboardMarkup(permanent_keyboard, resize_keyboard=True)

    await query.message.reply_text(
        text=metrics_text,
        reply_markup=permanent_reply_markup,
        parse_mode='HTML'
    )

# --- THIS IS THE CHANGE ---
async def show_metrics_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the press of the PERMANENT button by sending the metrics directly."""
    # First, get the data. The user will see the "typing..." status.
    metrics_text = await get_metrics_text()
    # Then, send the final message in one go.
    await update.message.reply_text(text=metrics_text, parse_mode='HTML')


async def handle_generic_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("I don't understand that. Please use the '📊 Sentient Metrics' button.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI app starting up...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_metrics_callback, pattern='^show_metrics$'))
    application.add_handler(MessageHandler(filters.Text(["📊 Sentient Metrics"]), show_metrics_from_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_generic_message))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram bot is running in the background.")
    yield
    logger.info("FastAPI app shutting down...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("Telegram bot has been shut down.")

app = FastAPI(
    lifespan=lifespan,
    title="Telegram User API & Bot"
)

# --- API ENDPOINTS (Unchanged) ---
@app.get("/users/ids/", response_model=List[int], tags=["Users"])
def get_all_user_ids_endpoint(db: Session = Depends(get_db)):
    return crud.get_all_user_ids(db)

@app.delete("/users/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"])
def remove_user_endpoint(chat_id: int, db: Session = Depends(get_db)):
    was_removed = crud.remove_user(db, chat_id=chat_id)
    if not was_removed:
        raise HTTPException(status_code=404, detail="User not found")
    return None
