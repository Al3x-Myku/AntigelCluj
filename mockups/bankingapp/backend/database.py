"""Database connection — MongoDB via PyMongo."""

import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "bankingapp")

client = MongoClient(MONGO_URI)
db = client[MONGO_DATABASE]

# Collections
users_col = db["users"]
bank_accounts_col = db["bank_accounts"]
cards_col = db["cards"]
api_keys_col = db["api_keys"]


def init_db():
    """Create indexes for performance."""
    users_col.create_index("email", unique=True)
    bank_accounts_col.create_index("user_id")
    bank_accounts_col.create_index("iban", unique=True)
    cards_col.create_index("user_id")
    cards_col.create_index("card_number", unique=True)
    api_keys_col.create_index("user_id")
    api_keys_col.create_index("key", unique=True)


def get_db():
    """FastAPI dependency — returns the MongoDB database."""
    return db
