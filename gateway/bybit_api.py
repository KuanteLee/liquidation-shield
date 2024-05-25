import os
import time
import urllib.parse
import requests
import hashlib
import hmac

from dotenv import load_dotenv
load_dotenv()

class BybitHttp(object):
    """
    Class for making HTTP requests to the Bybit API.
    Ref: https://github.com/bybit-exchange/api-usage-examples/blob/master/V5_demo/api_demo/Encryption_HMAC.py
    """

    def __init__(self):
        """
        Initialize BybitHttp with API key, API secret, and base URL.
        """
        self.API_KEY = os.getenv("BYBIT_API_KEY")
        self.API_SECRET = os.getenv("BYBIT_API_SECRET")
        self.BASE_URL = "https://api.bybit.com"
        os.environ['NO_PROXY'] = self.BASE_URL
        # Ref: https://www.cnblogs.com/Eeyhan/p/14610998.html
        
        self.recv_window = str(5000)
        self.http_client = requests.Session()

    def _gen_signature(self, payload: str, time_stamp: str) -> str:
        """
        Generate HMAC signature for request authentication.

        Args:
            payload (str): Request payload.
            time_stamp (str): Current timestamp.

        Returns:
            str: HMAC signature.
        """
        param_str = f"{time_stamp}{self.API_KEY}{self.recv_window}{payload}"
        hash_obj = hmac.new(
            bytes(self.API_SECRET, "utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256
        )
        signature = hash_obj.hexdigest()
        return signature

    def http_request(self, endpoint: str, method: str, payload: dict) -> str:
        """
        Make an HTTP request to the Bybit API.

        Args:
            endpoint (str): API endpoint.
            method (str): HTTP method (GET or POST).
            payload (dict): Request payload.

        Returns:
            str: Response text.
        """
        # Encode payload for GET requests
        if method == "GET":
            payload = urllib.parse.urlencode(payload)

        # Generate timestamp and signature
        time_stamp = str(int(time.time() * 10 ** 3))
        signature = self._gen_signature(payload, time_stamp)

        # Set request headers
        headers = {
            'X-BAPI-API-KEY': self.API_KEY,
            'X-BAPI-SIGN': signature,
            'X-BAPI-SIGN-TYPE': '2',
            'X-BAPI-TIMESTAMP': time_stamp,
            'X-BAPI-RECV-WINDOW': self.recv_window,
            'Content-Type': 'application/json'
        }

        # Make HTTP request
        if method == "POST":
            response = self.http_client.request(
                method, f"{self.BASE_URL}{endpoint}", headers=headers, data=payload)
        else:
            response = self.http_client.request(
                method, f"{self.BASE_URL}{endpoint}?{payload}", headers=headers)
            
        response = response.json()
        return response["result"] if response["retMsg"] == "OK" else response
    
    def get_position_info(self):

        endpoint = "/v5/position/list"
        method = "GET"
        params = {
            "category": "linear",
            # "symbol": "SAGAUSDT",
            "settleCoin": "USDT",
            # "limit": 1,
        }

        response = self.http_request(endpoint, method, params)
        return response

    def get_orderbook(self, symbol):

        endpoint = "/v5/market/orderbook"
        method = "GET"
        params = {
            "category": "spot",
            "symbol": symbol,
        }

        response = self.http_request(endpoint, method, params)
        return response
    
    def get_wallet_balance(self):

        endpoint = "/v5/account/wallet-balance"
        method = "GET"
        params = {
            "accountType": "UNIFIED",
            # "coin": "USDT",
        }

        response = self.http_request(endpoint, method, params)
        return response

    def get_risk_limit(self):

        endpoint = "/v5/market/risk-limit"
        method = "GET"
        params = {
            "category": "linear",
            "symbol": "SAGAUSDT",
        }

        response = self.http_request(endpoint, method, params)
        return response
