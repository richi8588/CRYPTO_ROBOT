# check_balance.py

from connectors.bybit_connector import BybitConnector
from config.settings import API_KEYS
from utils.logger import log

def check_balances():
    log.info("--- Checking Bybit Balances ---")

    bybit_api_key = API_KEYS['bybit']['api_key']
    bybit_api_secret = API_KEYS['bybit']['secret_key']

    if not bybit_api_key or bybit_api_key == 'YOUR_BYBIT_API_KEY' or \
       not bybit_api_secret or bybit_api_secret == 'YOUR_BYBIT_API_SECRET':
        log.error("Error: Bybit API keys are not properly configured.")
        log.error("Please set BYBIT_API_KEY and BYBIT_API_SECRET environment variables.")
        return

    connector = BybitConnector()

    log.info("Fetching USDT balance...")
    usdt_balance = connector.get_balance("USDT")
    if usdt_balance is not None:
        log.info(f"Successfully fetched USDT balance: {usdt_balance}")
    else:
        log.error("Failed to fetch USDT balance.")

    log.info("Fetching DOGE balance...")
    doge_balance = connector.get_balance("DOGE")
    if doge_balance is not None:
        log.info(f"Successfully fetched DOGE balance: {doge_balance}")
    else:
        log.error("Failed to fetch DOGE balance.")
    
    log.info("\n--- Check Complete ---")

if __name__ == "__main__":
    check_balances()
