# main.py
import os
import asyncio
from typing import List
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx

import crud
import models
import schemas
from database import SessionLocal, engine
#from apy_listener import check_for_yield_opportunities
#from telebot import broadcast_messages
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
# --- DATABASE AND APP SETUP ---

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Create DB tables on startup
models.Base.metadata.create_all(bind=engine)

# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
# --- TELEGRAM BOT SETUP ---

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

'''
async def market_monitor_worker():
    """A smart background task that checks for market changes and prevents spam."""
    logger.info("Market monitor worker started.")
    
    # This is the worker's "memory" to prevent spamming the same alert.
    last_sent_report = ""

    await asyncio.sleep(10) # Initial delay to allow the app to fully start

    while True:
        try:
            logger.info("Worker: Checking for yield opportunities...")
            report = await check_for_yield_opportunities()

            # --- THE CORE TRIGGER ---
            # Condition: Is there a real report AND is it different from the last one we sent?
            if "No action needed" not in report and report != last_sent_report:
                logger.info(f"Worker: New alert condition met! Broadcasting message.")
                
                # Get users from our database
                db = SessionLocal()
                try:
                    user_ids = crud.get_all_user_ids(db)
                finally:
                    db.close()

                # Broadcast the message
                await broadcast_messages(user_ids, report)
                
                # IMPORTANT: Update the memory with the new report
                last_sent_report = report
            
            elif "No action needed" in report:
                # If the market is optimal, clear the memory so we're ready for the next alert
                if last_sent_report:
                    logger.info("Worker: Market is now optimal. Clearing alert memory.")
                    last_sent_report = ""

            # Wait before the next cycle
            logger.info("Worker: Cycle complete. Sleeping for 60 seconds.")
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"An error occurred in the market monitor worker: {e}", exc_info=True)
            await asyncio.sleep(60) # Wait a minute before retrying on error
'''

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id

    db = SessionLocal()
    try:
        user_schema = schemas.UserCreate(chat_id=chat_id)
        db_user, created = crud.get_or_create_user(db, user_schema)

        if created:
            # New user
            message_text = (
                "🤖 Welcome to Sentient AI!\n\n"
                "Stay updated with live metrics anytime."
                "You can explore insights right away, "
                "Choose an option to get started:"
            )
        else:
            # Returning user
            message_text = "👋 Welcome back to Sentient AI!"
    finally:
        db.close()

    keyboard = [
        [InlineKeyboardButton("📊 Sentient Metrics", callback_data='show_metrics')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies to any text message that is not a command."""
    await update.message.reply_text("I'm sorry, I don't understand that. Send /start to subscribe.")

async def show_metrics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'show_metrics' button press by fetching and displaying APY data."""
    query = update.callback_query
    #await query.answer("Fetching metrics...")  # Acknowledge the button press
    
    try:
        async with httpx.AsyncClient() as client:
            # 1️⃣ General Vault Metrics (TVL)
            vault_url = API_URL
            vault_resp = await client.get(vault_url)
            vault_resp.raise_for_status()
            vault_data = vault_resp.json()

            # Calculate TVL
            tvl = 0.0
            for vault in vault_data:
                try:
                    tvl += float(vault.get("total_assets", 0))
                except (ValueError, TypeError):
                    continue
            tvl_formatted = f"${tvl:,.2f}"

            protocol_lines = []
            for vault in vault_data:
                try:
                    name = f"{vault['protocol']} {vault['token']}"
                    tvl_val = float(vault.get("total_assets", 0))
                    tvl_str = f"${tvl_val:,.2f}"
                    
                    # Calculate percentage based on the total_tvl
                    percent = (tvl_val / tvl * 100) if tvl > 0 else 0
                    protocol_lines.append(f"• {name}: {tvl_str} ({percent:.1f}%)")
                except (ValueError, TypeError, KeyError):
                    continue

            protocol_distribution = "\n".join(protocol_lines)

            # Construct the final message
            metrics_message = (
                "<b>📊 Sentient Metrics</b>\n\n"
                "<b>General Metrics:</b>\n"
                f"• TVL: {tvl_formatted}\n\n"
                "<b>Our Distribution:</b>\n"
                f"{protocol_distribution}"
            )
            
            # 5. Edit the original message to show the metrics
            await query.edit_message_text(text=metrics_message, parse_mode='HTML')

    except httpx.RequestError as e:
        logger.error(f"Error calling the metrics API: {e}")
        await query.edit_message_text(
            text="😕 Sorry, the metrics service seems to be down. Please try again later."
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred in show_metrics_handler: {e}")
        await query.edit_message_text(
            text="😕 An unexpected error occurred. Please try again later."
        )

# --- FASTAPI LIFESPAN MANAGER ---
# This part of the code tells FastAPI what to do on startup and shutdown.

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI app starting up...")
    
    # Build and start the Telegram bot listener
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(show_metrics_handler, pattern='^show_metrics$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram bot is running in the background.")
    
    # NEW: Start the market monitor background worker
    #asyncio.create_task(market_monitor_worker())
    
    yield # The application is now running
    
    # On shutdown...
    logger.info("FastAPI app shutting down...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    logger.info("Telegram bot has been shut down.")

# --- CREATE FASTAPI APP ---
# We pass the lifespan manager to the FastAPI app.

app = FastAPI(
    lifespan=lifespan,
    title="Telegram User API & Bot",
    description="An API to manage Telegram bot users, with an integrated bot listener.",
    version="1.0.0"
)

# --- API ENDPOINTS (They still work!) ---

@app.get("/users/ids/", response_model=List[int], tags=["Users"])
def get_all_user_ids_endpoint(db: Session = Depends(get_db)):
    """
    Returns a list of all subscribed user chat_ids.
    """
    return crud.get_all_user_ids(db)

@app.delete("/users/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"])
def remove_user_endpoint(chat_id: int, db: Session = Depends(get_db)):
    """
    Removes a user by their chat_id.
    """
    was_removed = crud.remove_user(db, chat_id=chat_id)
    if not was_removed:
        raise HTTPException(status_code=404, detail="User not found")
    return None