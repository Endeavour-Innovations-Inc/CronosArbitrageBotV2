import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

# Read environment variables
NETWORK_RPC = os.getenv('NETWORK_RPC')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
