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
VAULT_API_URL = os.getenv("VAULT_API_URL")
YIELD_API_URL = os.getenv("YIELD_API_URL")
REBALANCE_CHECK_INTERVAL_SECONDS = int(os.getenv("REBALANCE_CHECK_INTERVAL_SECONDS", 60))

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
                "🤖 Welcome to Neura Vault!\n\n"
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
                "🤖 Welcome to Neura Vault!\n\n"
                "You are now subscribed. Tap the button below to get your first metrics update."
            )
        else:
            message_text = "👋 Welcome back! Tap the button for the latest metrics."

    keyboard = [[InlineKeyboardButton("📊 Neura Metrics", callback_data='show_metrics')]]
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
                "<b>📊 Neura Metrics</b>\n\n"
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

    permanent_keyboard = [[KeyboardButton("📊 Neura Metrics")]]
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

def format_rebalancing_message(rebalance_event: dict) -> str | None:
    """Formats a rebalance event into a notification message."""
    try:
        amount = float(rebalance_event['amount_token'])
        token_symbol = rebalance_event['token_symbol']
        from_protocol = rebalance_event['from_protocol']
        to_protocol = rebalance_event['to_protocol']
        tx_hash = rebalance_event['deposit_transaction']['transaction_hash']
        strategy_summary = rebalance_event.get('strategy_summary', 'No summary provided.').strip().strip('"')
        tx_link = f"https://hyperevmscan.io/tx/0x{tx_hash}"
        message = (
            f"⚡️ **Yield Optimized**\n\n"
            f"A {amount:.6f} {token_symbol} position was moved to capture higher yield.\n\n"
            f"**From:** `{from_protocol}`\n"
            f"**To:** `{to_protocol}`\n\n"
            f"**Reason:**\n"
            f"> {strategy_summary}\n\n"
            f"Automated by Neura.\n"
            f"[View Transaction]({tx_link})"
        )
        return message
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Failed to format rebalance message: {e}")
        return None

async def handle_generic_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("I don't understand that. Please use the '📊 Neura Metrics' button.")

async def broadcast_rebalance_message(application: Application, message: str):
    """Sends a message to all subscribed users."""
    logger.debug("BROADCAST: Getting database session...")
    db = next(get_db())
    try:
        logger.debug("BROADCAST: Fetching all user IDs from DB...")
        user_ids = await asyncio.to_thread(crud.get_all_user_ids, db)
        logger.info(f"BROADCAST: Found {len(user_ids)} users to notify.")
    finally:
        db.close()
    
    if not user_ids:
        logger.warning("BROADCAST: No users found, skipping broadcast.")
        return

    logger.info(f"BROADCAST: Sending message to {len(user_ids)} users concurrently...")
    tasks = [application.bot.send_message(chat_id=uid, text=message, parse_mode='Markdown') for uid in user_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for res in results if not isinstance(res, Exception))
    logger.info(f"BROADCAST: Finished. {success_count}/{len(user_ids)} messages sent successfully.")

async def check_and_notify_rebalance(application: Application):
    """The core logic that checks for new rebalances and triggers notifications."""
    logger.info("BACKGROUND TASK: Checking for new rebalance event...")
    api_url = f"{YIELD_API_URL}/api/vault/rebalances/combined/"
    params = {"page_size": 1}
    db = next(get_db())
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, params=params, timeout=20)
            if response.status_code != 200:
                logger.error(f"Yield API Error: {response.status_code}")
                return
            latest_event = response.json()[0]
        
        latest_rebalance_id = latest_event['rebalance_id']
        logger.info(f"Latest rebalance event ID: {latest_rebalance_id}")

        # Check if we've already processed this event
        logger.debug(f"CHECKER: Checking database for event ID {latest_rebalance_id}...")
        event_exists = await asyncio.to_thread(crud.get_rebalance_event_by_rebalance_id, db, latest_rebalance_id)
        if event_exists:
            logger.info("No new rebalance event found.")
            return
        logger.info(f"CHECKER: New rebalance event found: {latest_rebalance_id}. Preparing notification.")
        message = format_rebalancing_message(latest_event)
        if message:
            await broadcast_rebalance_message(application, message)
            # After sending, save the record to the database
            event_to_create = schemas.RebalanceEventCreate(
                rebalance_id=latest_rebalance_id,
                transaction_hash=latest_event['deposit_transaction']['transaction_hash']
            )
            await asyncio.to_thread(crud.create_rebalance_event, db, event_to_create)
            logger.info(f"Successfully processed and saved event {latest_rebalance_id}.")

    except (httpx.RequestError, IndexError, KeyError) as e:
        logger.error(f"Error during rebalance check: {e}")
    finally:
        db.close()

async def run_rebalance_check_periodically(application: Application):
    """The background task that runs indefinitely."""
    while True:
        #await check_and_notify_rebalance(application)
        await check_and_notify_rebalance_mock(application)
        logger.info(f"BACKGROUND TASK: Sleeping for {REBALANCE_CHECK_INTERVAL_SECONDS} seconds.")
        await asyncio.sleep(REBALANCE_CHECK_INTERVAL_SECONDS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI app starting up...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_metrics_callback, pattern='^show_metrics$'))
    application.add_handler(MessageHandler(filters.Text(["📊 Neura Metrics"]), show_metrics_from_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_generic_message))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram bot is running in the background.")
    logger.info(f"Starting periodic rebalance checker. Interval: {REBALANCE_CHECK_INTERVAL_SECONDS} seconds.")
    rebalance_task = asyncio.create_task(run_rebalance_check_periodically(application))
    yield
    logger.info("FastAPI app shutting down...")
    rebalance_task.cancel()
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

@app.get("/rebalance-events/{rebalance_id}", response_model=schemas.RebalanceEvent)
def read_rebalance_event(rebalance_id: str, db: Session = Depends(get_db)):
    """
    Checks if a rebalance event exists by its rebalance_id.
    Returns the event if found, otherwise returns a 404 error.
    """
    db_event = crud.get_rebalance_event_by_rebalance_id(db, rebalance_id=rebalance_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Rebalance event not found")
    return db_event

@app.post("/rebalance-events/", response_model=schemas.RebalanceEvent, status_code=201)
def create_rebalance_event(event: schemas.RebalanceEventCreate, db: Session = Depends(get_db)):
    """
    Creates a new rebalance event record.
    Prevents creating duplicates.
    """
    db_event = crud.get_rebalance_event_by_rebalance_id(db, rebalance_id=event.rebalance_id)
    if db_event:
        raise HTTPException(status_code=409, detail="Rebalance event already exists")
    return crud.create_rebalance_event(db=db, event=event)
