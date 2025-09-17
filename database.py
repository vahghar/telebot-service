# database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import asynccontextmanager

load_dotenv() # Load environment variables from .env file

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# The engine is the main entry point to the database for SQLAlchemy
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_size=20, max_overflow=30, pool_timeout=30)

# Each instance of SessionLocal will be a new database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base will be used to create our database models (the tables)
Base = declarative_base()

# ------------------- ADD THIS SECTION -------------------
@asynccontextmanager
async def get_async_db() -> Session:
    """
    An async context manager to handle database sessions automatically.
    This is the "expert assistant" for your bot handlers.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# --------------------------------------------------------