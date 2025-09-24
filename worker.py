# worker.py (new file)
import asyncio
import logging
from telegram.ext import Application

import crud
import schemas
from main import (
    TELEGRAM_TOKEN, REDIS_SETTINGS, format_rebalancing_message, 
    broadcast_rebalance_message
)
from database import get_async_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def on_startup(ctx):
    """
    This runs once when the worker starts.
    We'll create the Telegram bot application instance here.
    """
    logger.info("Worker starting up...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    await application.initialize()
    await application.start()
    # Store the application instance in the worker's context
    ctx['telegram_application'] = application
    logger.info("Telegram application initialized in worker.")

async def on_shutdown(ctx):
    """This runs once when the worker shuts down."""
    logger.info("Worker shutting down...")
    application = ctx.get('telegram_application')
    if application:
        await application.stop()
        await application.shutdown()
    logger.info("Telegram application shut down in worker.")


async def process_rebalance(ctx, payload: dict):
    """
    This is the background job that processes the rebalance event.
    ARQ will call this function for every job in the queue.
    """
    rebalance_id = payload.get('rebalance_id', 'N/A')
    logger.info(f"WORKER: Processing job for rebalance event ID: {rebalance_id}")
    
    # Get the Telegram application from the context we created on startup
    application = ctx['telegram_application']

    deposit_hash = payload.get('deposit_transaction', {}).get('transaction_hash')
    withdrawal_hash = payload.get('withdrawal_transaction', {}).get('transaction_hash')

    tx_hash = deposit_hash or withdrawal_hash

    # 1. Check if event was already processed to avoid duplicates
    async with get_async_db() as db:
        event_exists = await asyncio.to_thread(crud.get_rebalance_event_by_rebalance_id, db, rebalance_id)
        if event_exists:
            logger.warning(f"WORKER: Event {rebalance_id} already processed. Job skipped.")
            return # Exit gracefully

        # If not, save it now before we try to notify
        #tx_hash = payload.get('deposit_transaction', {}).get('transaction_hash') or "missing_hash"
        event_to_create = schemas.RebalanceEventCreate(rebalance_id=rebalance_id, transaction_hash=tx_hash)
        await asyncio.to_thread(crud.create_rebalance_event, db, event_to_create)

    # 2. Format the message
    message = format_rebalancing_message(payload)
    if not message:
        # If formatting fails, we can't proceed.
        logger.error(f"WORKER: Failed to format message for event {rebalance_id}. Aborting job.")
        return

    # 3. Broadcast the message
    try:
        await broadcast_rebalance_message(application, message)
        logger.info(f"WORKER: Successfully broadcasted message for event {rebalance_id}.")
    except Exception as e:
        logger.error(f"WORKER: Broadcast failed for event {rebalance_id}: {e}", exc_info=True)
        # ARQ will retry the job automatically based on its settings
        raise # Re-raise the exception to trigger a retry

# This class defines the worker's settings for ARQ
class WorkerSettings:
    functions = [process_rebalance]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = REDIS_SETTINGS