import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from app.core.settings import settings

load_dotenv()

DATABASE_URL = settings.SQLALCHEMY_DATABASE_URL

"""
The engine manages the connection to the database and handles query execution.
"""
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
