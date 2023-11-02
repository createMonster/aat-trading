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
        return requests.get(f"{self.api_url}/products", auth=self).json()
    
    def _accounts(self) -> dict:
        """fetch a list of accounts from coinbase rest api"""
        return requests.get(f"{self.api_url}/accounts", auth=self).json()

    def _account(self, account_id: str) -> dict:
        """fetch single account info from coinbase rest api"""
        return requests.get(
            f"{self.api_url}/accounts/{account_id}", auth=self
        ).json()
    
    def _newOrder(self, order_json: dict) -> str:
        """create a new order"""

        # post my order to the rest endpoint
        res = requests.post(
            f"{self.api_url}/orders", json=order_json, auth=self
        )

        # if successful, return the new order id
        if res.status_code == 200:
            # TODO what if filled immediately?
            return res.json()["id"]

        # TODO    
        return ""
    
    def _orderBook(self, id: str) -> dict:
        # fetch an instrument's level 3 orderbook from rest api
        return requests.get(
            f"{self.api_url}/products/{id}/book?level=3", auth=self
        ).json()
    
    @lru_cache(None)
    def instruments(self) -> List[Instrument]:
        """construct a list of instruments from the coinbase-returned json list of instruments"""
        ret = []
        
        # this will fetch a list of pairs
        products = self._products()
        
        for product in products:
            # separate pair into base and quote
            first = product["base_currency"]
            second = product["quote_currency"]

            # for each pair, construct both underlying currencies as well as
            # the pair object
            ret.append(
                Instrument(
                    name="{}-{}".format(first, second),
                    type=InstrumentType.PAIR,
                    exchange=self.exchange,
                    broker_id=product["id"],
                    leg1=self.currency(first),
                    leg2=self.currency(second),
                    leg1_side=Side.BUY,
                    leg2_side=Side.SELL,
                    price_increment=float(product["base_increment"]),
                )
            )

        return ret
    
    @lru_cache(None)
    def currency(self, symbol: str) -> Instrument:
        # construct a base currency from the symbol
        return Instrument(name=symbol, type=InstrumentType.CURRENCY)
    
    @lru_cache(None)
    async def accounts(self) -> List[Position]:
        """fetch a list of coinbase accounts. These store quantities of InstrumentType.CURRENCY"""
        ret = []
        
        # fetch all accounts
        accounts = self._accounts()

        # if unauthorized or invalid api key, raise
        if accounts == {"message": "Unauthorized."} or \
            accounts == {"message": "Invalid API Key"}:
            raise Exception("Coinbase Auth Failed")
        
        # for each account
        for account in accounts:
            # grab the id to lookup info
            acc_data = self._account(account["id"])

            # if tradeable and positive balance
            if acc_data["trading_enabled"] and float(acc_data["balance"]) > 0:
                # construct a position representing the balance
                
                pos = Position(
                    float(acc_data["balance"]) * self._multiple,
                    0.0,
                    datetime.now(),
                    Instrument(
                        acc_data["currency"],
                        InstrumentType.CURRENCY,
                        exchange=self.exchange,
                    ),
                    self.exchange,
                    []
                )
                ret.append(pos)

        return ret

    async def newOrder(self, order: Order) -> bool:
        """given an aat order, construct a coinbase order json"""
        pass