import os
import time
import hmac
import urllib
import hashlib
import requests

from decimal import Decimal
from enum import Enum
from dotenv import load_dotenv
load_dotenv()

# Ref: https://stackoverflow.com/questions/28521535/requests-how-to-disable-bypass-proxy
os.environ['NO_PROXY'] = '*'

# default setting
TRY_COUNTS: int = 1
API_TIMEOUT: int = 5

class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"


class RequestMethod(Enum):
    """
    请求的方法.
    """
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class AcountType(Enum):
    SPOT = "SPOT"
    FUND = "FUND"


class BinanceHttp(object):
    """
    Documentation: https://binance-docs.github.io/apidocs/futures/en/#change-log
    """

    def __init__(self):
        self.timeout: int = API_TIMEOUT
        self.try_counts: int = TRY_COUNTS
    
    def _request(self, req_method: RequestMethod, path: str, params: dict=None):

        url = self.BASE_URL + path

        for param in list(params.keys()):
            if params[param] == True:
                params[param] = "true"
            elif params[param] == False:
                params[param] = "false"

        query_str = urllib.parse.urlencode(params)

        if params:
            signature = self._sign(query_str)
            url += f'?{query_str}&signature={signature}'

        headers = {
            "X-MBX-APIKEY": self.API_KEY
        }

        for _ in range(self.try_counts):

            try:
                response = requests.request(req_method.value, url=url, headers=headers, timeout=self.timeout)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(response.json(), response.status_code)

            except Exception as error:
                print(f"请求:{path}, 发生了错误: {error}")
                time.sleep(1.5)

        return None

    def _get_current_timestamp(self) -> str:
        return str(int(time.time() * 1000))

    def _sign(self, query_str: str) -> str:
        hex_digest = hmac.new(
            self.SECRET_KEY.encode('utf8'), query_str.encode("utf-8"), hashlib.sha256).hexdigest()
        return str(hex_digest)


class BinanceUSDFeatureHttp(BinanceHttp):

    def __init__(self, timeout: int=API_TIMEOUT, try_counts: int=TRY_COUNTS):

        self.API_KEY: str = os.getenv("BINANCE_API_KEY")
        self.SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY")
        self.BASE_URL: str = "https://fapi.binance.com"

        self.timeout: int = timeout
        self.try_counts: int = try_counts
    
    def get_account_information_v2(self):
        """ 账户信息V2 (USER_DATA) """
        
        path = "/fapi/v2/account"
        method = RequestMethod.GET

        params = {
            "timestamp": self._get_current_timestamp(),
        }

        return self._request(method, path, params)

    def modify_isolated_position_margin(self, symbol: str, amount: Decimal, type: int):
        """ 
        调整逐仓保证金 (TRADE): 针对逐仓模式下的仓位，调整其逐仓保证金资金。

        Args:
            type (int): 调整方向
                - 1: 增加逐仓保证金
                - 2: 减少逐仓保证金
        """

        path = "/fapi/v1/positionMargin"
        method = RequestMethod.POST

        params = {
            "symbol": symbol,
            "amount": amount,
            "type": str(type),
            "timestamp": self._get_current_timestamp(),
        }

        return self._request(method, path, params)


class BinanceSpotHttp(BinanceHttp):
    
    def __init__(self, timeout: int=API_TIMEOUT, try_counts: int=TRY_COUNTS):

        self.API_KEY: str = os.getenv("BINANCE_API_KEY")
        self.SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY")
        self.BASE_URL: str = "https://api.binance.com"

        self.timeout: int = timeout
        self.try_counts: int = try_counts

    def get_flexible_product_position(self, **kwargs):
        """ 获取活期产品持仓(USER_DATA) """

        path = "/sapi/v1/simple-earn/flexible/position"
        method = RequestMethod.GET

        params = {
            "timestamp": self._get_current_timestamp(),
        }  

        for param in list(kwargs.keys()):
            params[param] = kwargs[param]

        return self._request(method, path, params)
    
    def redeem_flexible_product(self, productId, **kwargs):
        """ 赎回活期产品 (TRADE): 频次限制：每个账户最多三秒一次 """

        path = "/sapi/v1/simple-earn/flexible/redeem"
        method = RequestMethod.POST

        params = {
            "timestamp": self._get_current_timestamp(),
            "productId": productId,
        }  

        for param in list(kwargs.keys()):
            params[param] = kwargs[param]

        return self._request(method, path, params)
    
    def new_future_account_transfer(self, asset: str, amount: Decimal, type: int):
        """ 合约资金划转 (USER_DATA): 执行现货账户与合约账户之间的划转 
        
        Args:
            type (int):
                - 1: 现货账户向USDT合约账户划转  
                - 2: USDT合约账户向现货账户划转  
                - 3: 现货账户向币本位合约账户划转  
                - 4: 币本位合约账户向现货账户划转  
        """

        path = "/sapi/v1/futures/transfer"
        method = RequestMethod.POST

        params = {
            "timestamp": self._get_current_timestamp(),
            "asset": asset,
            "amount": amount,
            "type": str(type),
        } 

        return self._request(method, path, params)
    
    def get_account_information(self, **kwargs):
        """ 账户信息 (USER_DATA): 获取当前账户信息 """
        
        path = "/api/v3/account"
        method = RequestMethod.GET

        params = {
            "timestamp": self._get_current_timestamp(),
        } 

        for param in list(kwargs.keys()):
            params[param] = kwargs[param]

        return self._request(method, path, params)

    def flexible_loan_borrow(self, loan_coin: str, loan_amount: Decimal, collateral_coin: str):
        
        path = "/sapi/v2/loan/flexible/borrow"
        method = RequestMethod.POST

        params = {
            "loanCoin": loan_coin,
            "loanAmount": str(loan_amount), 
            "collateralCoin": collateral_coin,
            "timestamp": self._get_current_timestamp(),
        } 

        return self._request(method, path, params)
    
    def get_flexible_loan_ongoing_orders(self, **kwargs):
        
        path = "/sapi/v2/loan/flexible/ongoing/orders"
        method = RequestMethod.GET

        params = {
            "timestamp": self._get_current_timestamp(),
        } 

        for param in list(kwargs.keys()):
            params[param] = kwargs[param]

        return self._request(method, path, params)

