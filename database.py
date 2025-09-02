# database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv() # Load environment variables from .env file

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# The engine is the main entry point to the database for SQLAlchemy
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Each instance of SessionLocal will be a new database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base will be used to create our database models (the tables)
Base = declarative_base()