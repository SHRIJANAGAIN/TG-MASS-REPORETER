import asyncio
import json
import random
import logging
import os
import time
from telethon import TelegramClient
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import InputReportReasonSpam
from telethon.errors import FloodWaitError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Corrected and simplified ASCII art for "Telegram Reporter"
TELEGRAM_REPORTER = """
▀█▀  █▀▀    █▀█  █▀▀  █▀█  █▀█  █▀█  ▀█▀  █▀▀  █▀█
░█░  █▄█    █▀▄  ██▄  █▀▀  █▄█  █▀▄  ▀█▀  ██▄  █▀

TG REPORTER

SCRIPT BY SHRIWARDHAN TIWARI
"""

# ANSI color codes
GOLDEN_TEXT = "\033[93m"  # Bright yellow text
RESET = "\033[0m"  # Reset all
BACKGROUND_COLORS = [
    "\033[44m",  # Blue
    "\033[45m",  # Pink (magenta)
    "\033[40m",  # Black
    "\033[43m",  # Golden (yellow)
    "\033[47m"   # White
]

# Clear screen function (cross-platform)
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# Load accounts from a JSON file
def load_accounts(file_path='accounts.json'):
    try:
        with open(file_path, 'r') as f:
            accounts = json.load(f)
        if not accounts:
            raise ValueError("No accounts found in accounts.json")
        return accounts
    except FileNotFoundError:
        logging.error("accounts.json not found. Please create it with account details.")
        return []
    except json.JSONDecodeError:
        logging.error("Invalid JSON format in accounts.json.")
        return []

# Load proxies from a JSON file
def load_proxies(file_path='proxies.json'):
    try:
        with open(file_path, 'r') as f:
            proxies = json.load(f)
        return proxies
    except FileNotFoundError:
        logging.error("proxies.json not found. Running without proxies.")
        return []
    except json.JSONDecodeError:
        logging.error("Invalid JSON format in proxies.json.")
        return []

async def initialize_client(account, proxy=None):
    """Initialize a Telegram client for a single account with optional proxy."""
    try:
        proxy_config = None
        if proxy:
            proxy_type = proxy.get('type', 'socks5')
            if proxy_type == 'socks5':
                proxy_config = (
                    'socks5',
                    proxy['host'],
                    proxy['port'],
                    proxy.get('username'),
                    proxy.get('password')
                )
            else:
                logging.error(f"Unsupported proxy type {proxy_type} for {account['phone']}. Ignoring proxy.")
                proxy_config = None
        
        client = TelegramClient(
            account['session_name'],
            account['api_id'],
            account['api_hash'],
            proxy=proxy_config
        )
        await client.start(phone=account['phone'])
        if await client.is_user_authorized():
            proxy_info = f"with proxy {proxy['host']}:{proxy['port']}" if proxy else "without proxy"
            logging.info(f"Successfully logged in with {account['phone']} {proxy_info}")
            return client
        else:
            logging.error(f"Failed to log in with {account['phone']}: Not authorized")
            return None
    except Exception as e:
        logging.error(f"Error logging in with {account['phone']}: {e}")
        return None

async def report_channel(client, phone, channel_username):
    """Report a Telegram channel for a given client."""
    try:
        peer = await client.get_input_entity(channel_username)
        result = await client(ReportPeerRequest(
            peer=peer,
            reason=InputReportReasonSpam(),
            message=f"Reported by {phone} for spam content"
        ))
        logging.info(f"Successfully reported {channel_username} with {phone}")
        return True
    except FloodWaitError as e:
        wait_time = e.seconds
        logging.error(f"Flood wait error for {phone}: Waiting {wait_time} seconds")
        await asyncio.sleep(wait_time)
        return False
    except Exception as e:
        logging.error(f"Error reporting {channel_username} with {phone}: {e}")
        return False

async def process_account(account, channel_username, proxy, semaphore):
    """Process a single account with rate limiting and optional proxy."""
    async with semaphore:
        client = await initialize_client(account, proxy)
        if client:
            async with client:
                success = await report_channel(client, account['phone'], channel_username)
                await asyncio.sleep(random.uniform(0.5, 1.0))
                return success
        return False

async def main():
    """Main function to handle multiple accounts and report a channel with changing background."""
    color_index = 0
    while True:
        # Clear screen and set new background
        clear_screen()
        
        # Cycle through background colors with a visible delay
        current_bg = BACKGROUND_COLORS[color_index % len(BACKGROUND_COLORS)]
        print(f"{current_bg}{GOLDEN_TEXT}{TELEGRAM_REPORTER}{RESET}")
        time.sleep(2)  # Longer delay to ensure color change is visible
        print(f"{current_bg}Press any key to continue...{RESET}")
        input()  # Wait for user input to proceed

        # Load accounts and proxies
        accounts = load_accounts()
        proxies = load_proxies()
        if not accounts:
            logging.error("No valid accounts loaded. Exiting.")
            return

        # Prompt for channel username
        target_channel = input(f"{current_bg}Enter channel username (e.g., @channelname): {RESET}").strip()
        if not target_channel.startswith('@'):
            target_channel = '@' + target_channel

        # Prompt for number of reports
        print(f"{current_bg}Loaded {len(accounts)} accounts.{RESET}")
        try:
            num_reports = int(input(f"{current_bg}Enter number of reports to perform (1 to {len(accounts)}): {RESET}"))
            if num_reports < 1:
                num_reports = len(accounts)
            if num_reports > len(accounts):
                num_reports = len(accounts)
        except ValueError:
            logging.info(f"Invalid input for number of reports. Using all {len(accounts)} accounts.")
            num_reports = len(accounts)

        logging.info(f"Planning to perform {num_reports} reports on {target_channel}.")

        # Select accounts for reporting
        selected_accounts = accounts[:num_reports]

        # Assign proxies to accounts
        account_proxy_pairs = []
        for i, account in enumerate(selected_accounts):
            proxy = proxies[i % len(proxies)] if proxies else None
            account_proxy_pairs.append((account, proxy))

        # Confirm user intent
        print(f"{current_bg}You are about to report {target_channel} with {len(selected_accounts)} accounts.{RESET}")
        print(f"{current_bg}Using {len(proxies)} proxies.{RESET}" if proxies else f"{current_bg}No proxies configured.{RESET}")
        confirmation = input(f"{current_bg}Type 'YES' to proceed or any other key to cancel: {RESET}")
        if confirmation.upper() != 'YES':
            logging.info("Operation cancelled by user.")
            return

        # Limit concurrent connections
        semaphore = asyncio.Semaphore(max(50, len(selected_accounts) // 2))
        tasks = [process_account(account, target_channel, proxy, semaphore)
                 for account, proxy in account_proxy_pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Summarize results
        successful_reports = sum(1 for result in results if result is True)
        logging.info(f"Completed: {successful_reports}/{len(selected_accounts)} accounts successfully reported {target_channel}")

        # Change color for the next iteration or break
        color_index += 1
        if input(f"{current_bg}Press Enter to run again or type 'exit' to quit: {RESET}").lower() == 'exit':
            break

if __name__ == "__main__":
    asyncio.run(main())