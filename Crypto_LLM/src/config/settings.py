# Standardized Exchange Settings (Public/Anonymous Mode)
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

EXCHANGE_ID = "bybit"
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")