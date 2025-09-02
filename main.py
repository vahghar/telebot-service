# main.py
import os
import asyncio
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import crud
import models
import schemas
from database import SessionLocal, engine

# --- DATABASE AND APP SETUP ---

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
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command. Saves the user to the DB directly."""
    chat_id = update.message.chat_id
    
    # Create a new database session for this function
    db = SessionLocal()
    try:
        # Create a user schema and call the crud function directly
        user_schema = schemas.UserCreate(chat_id=chat_id)
        db_user, created = crud.get_or_create_user(db, user_schema)
        
        if created:
            print(f"New user {chat_id} added to the database.")
        else:
            print(f"Existing user {chat_id} interacted with the bot.")

        await update.message.reply_text('Welcome! You are now subscribed.')
    finally:
        db.close() # Always close the session

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies to any text message that is not a command."""
    await update.message.reply_text("I'm sorry, I don't understand that. Send /start to subscribe.")


# --- FASTAPI LIFESPAN MANAGER ---
# This part of the code tells FastAPI what to do on startup and shutdown.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup...
    print("FastAPI app starting up...")
    
    # Build the Telegram bot application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run the bot in the background
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("Telegram bot is running in the background.")
    
    yield # The application is now running
    
    # On shutdown...
    print("FastAPI app shutting down...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    print("Telegram bot has been shut down.")


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