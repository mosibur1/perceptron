import os
import ctypes
import random
import asyncio
from typing import Optional
from asyncio.exceptions import CancelledError

import requests
import websockets
from colorama import Fore, Style, init

init(autoreset=True)

def print_banner():
    banner = """
    ╔════════════════════════╗
    ║      ██████╗███████╗    ║
    ║     ██╔════╝██╔════╝    ║
    ║     ██║     ███████╗    ║
    ║     ██║     ╚════██║    ║
    ║     ╚██████╗███████║    ║
    ║      ╚═════╝╚══════╝    ║
    ╚════════════════════════╝
    """
    print(Fore.CYAN + banner)
    print(Fore.GREEN + " https://t.me/ChainScripters" + Style.RESET_ALL)
    print("\n" + "="*60 + "\n")

class WebsocketClient:
    def __init__(self, session_id: str, proxy: Optional[str] = None):
        self.session_id = session_id
        self.proxy = proxy
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self):
        try:
            self.websocket = await websockets.connect(
                "wss://api.prod.blockmesh.io/ws",
                extra_headers={
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "origin": "https://app.blockmesh.io",
                },
                ping_interval=10,
                ping_timeout=20,
                max_queue=1,
                open_timeout=30,
            )
            await self.websocket.send(f"user:{self.session_id}")
            print(f"{Fore.GREEN}[Blockmesh] - Websocket connection established")
        except Exception as e:
            print(f"{Fore.RED}[Blockmesh] - Error connecting to websocket: {e}")
            raise

    async def receive_messages(self, on_message):
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                await on_message(message)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"{Fore.RED}[Blockmesh] - Websocket connection closed: {e}")
        except Exception as e:
            print(f"{Fore.RED}[Blockmesh] - Error receiving messages: {e}")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            print(f"{Fore.YELLOW}[Blockmesh] - Websocket connection closed")

class Blockmesh:
    def __init__(self, use_proxy):
        self.base_url = "https://api.prod.blockmesh.io"
        self.use_proxy = use_proxy
        self.proxies = self.load_proxies() if use_proxy else []
        self.accounts = self.load_accounts()
        self.websocket_client = None

    def load_accounts(self):
        with open("account.txt", "r") as f:
            return [line.strip().split(":") for line in f]

    def load_proxies(self):
        with open("proxies.txt", "r") as f:
            return [line.strip() for line in f]

    def get_proxy(self):
        return random.choice(self.proxies) if self.proxies else None

    async def login(self, email, password):
        url = f"{self.base_url}/v1/auth/login"
        headers = {"Content-Type": "application/json"}
        data = {"email": email, "password": password}
        proxy = self.get_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        try:
            response = await asyncio.to_thread(requests.post, url, headers=headers, json=data, proxies=proxies)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}[Blockmesh] - Login failed for {email}: {e}")
            return None

    async def get_user_profile(self, session_id):
        url = f"{self.base_url}/v1/users/profile"
        headers = {"Authorization": f"Bearer {session_id}"}
        proxy = self.get_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        try:
            response = await asyncio.to_thread(requests.get, url, headers=headers, proxies=proxies)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}[Blockmesh] - Failed to get user profile: {e}")
            return None

    async def handle_message(self, message):
        print(f"{Fore.CYAN}[Blockmesh] - Received message: {message}")

    async def process_account(self, email, password):
        print(f"{Fore.BLUE}[Blockmesh] - Processing account: {email}")
        login_data = await self.login(email, password)
        if not login_data:
            return

        session_id = login_data.get("token")
        if not session_id:
            print(f"{Fore.RED}[Blockmesh] - Failed to get session ID for {email}")
            return

        profile = await self.get_user_profile(session_id)
        if profile:
            wallet_address = profile.get("walletAddress", "N/A")
            print(f"{Fore.GREEN}[Blockmesh] - Login successful for {email} | Wallet: {wallet_address}")
            self.websocket_client = WebsocketClient(session_id, self.get_proxy())
            await self.websocket_client.connect()
            await self.websocket_client.receive_messages(self.handle_message)

    async def main(self):
        tasks = [self.process_account(email, password) for email, password in self.accounts]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    print_banner()
    use_proxy_input = input("Use proxies? (y/n): ").lower()
    use_proxy = use_proxy_input == 'y'

    if use_proxy:
        print(f"{Fore.YELLOW}Using proxies from proxies.txt")
    else:
        print(f"{Fore.YELLOW}Not using proxies")

    blockmesh = Blockmesh(use_proxy)
    try:
        asyncio.run(blockmesh.main())
    except CancelledError:
        print(f"{Fore.YELLOW}[Blockmesh] - Program interrupted. Closing websocket...")
        if blockmesh.websocket_client:
            asyncio.run(blockmesh.websocket_client.close())
