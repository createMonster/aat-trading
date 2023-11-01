import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List, Optional, Union, cast

import aiohttp
import requests
from requests import models

# from aat import Instrument, InstrumentType, Account, Position
from aat import (
    Event,
    EventType,
    ExchangeType,
    Instrument,
    InstrumentType,
    Order,
    OrderFlag,
    OrderType,
    Position,
    Side,
    Trade,
    TradingType,
)
from requests.auth import AuthBase

_REST = "https://api.pro.coinbase.com"
_WS = "wss://ws-feed.pro.coinbase.com"
_REST_SANDBOX = "https://api-public.sandbox.pro.coinbase.com"
_WS_SANDBOX = "wss://ws-feed-public.sandbox.pro.coinbase.com"

_SUBSCRIPTION: Dict[str, Union[str, List[str]]] = {
    "type": "subscribe",
    "product_ids": [],
    "channels": ["user", "heartbeat"],
}

class CoinbaseExchangeClient(AuthBase):
    def __init__(
        self,
        trading_type: TradingType,
        exchange: ExchangeType,
        api_key: str,
        secret_key: str,
        passphrase: str,
        satoshis: bool = False
    ) -> None:
        
        self.trading_type = trading_type
        
        # if running in sandbox mode, use sandbox url
        if self.trading_type == TradingType.SANDBOX:
            self.api_url = _REST_SANDBOX
            self.ws_url = _WS_SANDBOX
        else:
            self.api_url = _REST
            self.ws_url = _WS

        # the coinbase ExchangeType
        self.exchange = exchange

        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

        # multiply by 100,000,000 and do everything in integer volumes
        self._multiple = 100_000_000 if satoshis else 1.0

        # order_map
        self._order_map: Dict[str, Order] = {}

        # sequence number for order book
        self.seqnum: Dict[Instrument, int] = {}

    def __call__(self, request):
        # This is used by `requests` to sign the requests
        # in the coinbase specified auth scheme
        timestamp = str(time.time())
        message = (
            timestamp
            + request.method
            + request.path_url
            + (request.body or b"").decode()
        )
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode(), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode()

        request.headers.update(
            {
                "CB-ACCESS-SIGN": signature_b64,
                "CB-ACCESS-TIMESTAMP": timestamp,
                "CB-ACCESS-KEY": self.api_key,
                "CB-ACCESS-PASSPHRASE": self.passphrase,
                "Content-Type": "application/json",
            }
        )

        return request
    
    def _products(self) -> dict:
        """fetch list of products from coinbase rest api"""
        return requests.get(f"{self.api_url}/products").json()
    
    def _accounts(self) -> dict:
        """fetch a list of accounts from coinbase rest api"""
        return requests.get(f"{self.api_url}/accounts").json()