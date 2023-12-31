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
    
    def _cancelOrder(self, order_jsn: dict) -> bool:
        """delete an existing order"""
        # delete order with given order id
        resp = requests.delete(
            "{}/{}/{}?product_id={}".format(
                self.api_url, "orders", order_jsn["id"], order_jsn["product_id"]
            ),
            auth=self
        )

        # if successfully deleted, return True
        if resp.status_code == 200:
            return True
        # otherwise return false
        return False
    
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
        jsn: Dict[str, Union[str, int, float]] = {}
        jsn["product_id"] = order.instrument.name

        if order.order_type == OrderType.LIMIT:
            jsn["type"] = "limit"
            jsn["side"] = order.side.value.lower()
            jsn["price"] = order.price
            jsn["size"] = round(order.volume / self._multiple, 8)

            # From the coinbase docs
            if order.flag == OrderFlag.FILL_OR_KILL:
                jsn["time_in_force"] = "FOK"
            elif order.flag == OrderFlag.IMMEDIATE_OR_CANCEL:
                jsn["time_in_force"] = "IOC"
            else:
                jsn["time_in_force"] = "GTC"

        elif order.order_type == OrderType.MARKET:
            jsn["type"] = "market"
            jsn["side"] = order.side.value.lower()
            jsn["size"] = round(order.volume / self._multiple, 8)

        else:
            stop_order: Order = order.stop_target
            jsn["side"] = stop_order.side.value.lower()
            jsn["price"] = stop_order.price
            jsn["size"] = round(stop_order.volume / self._multiple, 8)

            if stop_order.side == Side.BUY:
                jsn["stop"] = "entry"
            else:
                jsn["stop"] = "loss"

            jsn["stop_price"] = order.price

            if stop_order.order_type == OrderType.LIMIT:
                jsn["type"] = "limit"
                if order.flag == OrderFlag.FILL_OR_KILL:
                    jsn["time_in_force"] = "FOK"
                elif order.flag == OrderFlag.IMMEDIATE_OR_CANCEL:
                    jsn["time_in_force"] = "IOC"
                else:
                    jsn["time_in_force"] = "GTC"

            elif stop_order.order_type == OrderType.MARKET:
                jsn["type"] = "market"

        # submit the order json
        id = self._newOrder(jsn)
        if id != "":
            # successful
            order.id = str(id)
            self._order_map[order.id] = order
            return True
        
        return False

    async def cancelOrder(self, order: Order) -> bool:
        # given an aat order, convert to json and cancel
        jsn = {}
        
        jsn["id"] = order.id
        jsn["product_id"] = cast(str. order.instrument.brokerId)
        return self._cancelOrder(jsn)
    
    async def orderBook(self, subscriptions: List[Instrument]
                        ) -> AsyncGenerator[Any, Event]:
        """fetch level 3 order book for each Instrument in our subscriptions"""
        for sub in subscriptions:
            # fetch the orderbook
            # order book is of form:
            #       {'bids': [[price, volume, id]],
            #        'asks': [[price, volume, id]],
            #        'sequence': <some positive integer>}
            ob = self._orderBook(cast(str, sub.brokerId))
            
            # set the last sequence number for when we connect to websocket later
            self.seqnum[sub] = ob["sequence"]

            # generate an open limit order for each bid
            for bid, qty, id in ob["bids"]:
                o = Order(
                    float(qty) * self._multiple,
                    float(bid),
                    Side.BUY,
                    sub,
                    self.exchange,
                    order_type=OrderType.LIMIT
                )
                yield Event(type=EventType.OPEN, target=o)

            # generate an open limit order for each ask
            for ask, qty, id in ob["asks"]:
                o = Order(
                    float(qty) * self._multiple,
                    float(ask),
                    Side.BUY,
                    sub,
                    self.exchange,
                    order_type=OrderType.LIMIT
                )
                yield Event(type=EventType.OPEN, target=o)

    async def websocket_l3(self, subscriptions: List[Instrument]):
        # copy the base subscription template
        subscription = _SUBSCRIPTION.copy()
        
        # fill in l3 details
        cast(List, subscription["channels"]).append("full")

        # for each subscription, add symbol to product_uds
        for sub in subscriptions:
            cast(List, subscription["product_ids"]).append(sub.brokerId)

        # sign the message in a similar way to the rest api, but
        # using the message of GET/users/self/verify
        timestamp = str(time.time())
        message = timestamp + "GET/users/self/verify"
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode(), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode()

        subscription.update(
            {
                "signature": signature_b64,
                "timestamp": timestamp,
                "key": self.api_key,
                "passphrase": self.passphrase,
            }
        )

        # construct a new websocket session
        session = aiohttp.ClientSession()
        
        # connect to the websocket
        async with session.ws_connect(self.ws_url) as ws:
            # send the subscription
            await ws.send_str(json.dumps(subscription))

            # for each message returned
            async for msg in ws:
                # only handle text message
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # load the data as json
                    x = json.loads(msg.data)

                    # skip earlier messages that our orderbook already reflects
                    if "sequence" in x:
                        inst = Instrument(
                            x["product_id"], InstrumentType.PAIR, self.exchange
                        )
                        if x.get("sequence", float("inf")) < self.seqnum.get(inst, 0):
                            # if msg has a sequence number, and that number is < the last sequence number
                            # ignore
                            continue

                    if x["type"] in ("subscriptions", "heartbeat"):
                        # TODO yield heartbeats?
                        continue

                    elif x["type"] == "received":
                        o = self._process_received(x)

                        if o:
                            # yield an open event for the new order
                            e = Event(type=EventType.OPEN, target=o)
                            yield e

                        elif x["type"] == "done":
                            o = cast(Order, self._process_done(x))
                            if o:
                                e = Event(type=EventType.CANCEL, target=o)
                                yield o
                        
                        elif x["type"] == "match":
                            o = cast(Order, self._process_match(x))
                            if o:
                                e = Event(type=EventType.TRADE, target=o)
                                yield o
                        
                        elif x["type"] == "open":
                            o = cast(Order, self._process_open(x))
                            if o:
                                e = Event(type=EventType.OPEN, target=o)
                                yield o
                        
                        elif x["type"] == "change":
                            o = cast(Order, self._process_change(x))
                            if o:
                                e = Event(type=EventType.CHANGE, target=o)
                                yield o
                        
                        elif x["type"] == "error":
                            pass
                        else:
                            # TODO unhandled
                            print ("TODO: unhandled")

    async def websocket_l2(self, subscriptions: List[Instrument]): 
        # copy the base subscription template
        subscription = _SUBSCRIPTION.copy()
        
        # fill in l2 details
        cast(List, subscription["channels"]).append("level2")

        # get trades
        cast(List, subscription["channels"]).append("ticker")

        # for each subcription, add symbol to product_ids
        for sub in subscriptions:
            cast(List, subscription["product_ids"]).append(sub.brokerId)

        # sign the message in a similar way to the rest api, but
        # using the message of GET/users/self/verify
        timestamp = str(time.time())
        message = timestamp + "GET/users/self/verify"
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode(), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode()

        # update the subscription message with the signing info
        subscription.update(
            {
                "signature": signature_b64,
                "timestamp": timestamp,
                "key": self.api_key,
                "passphrase": self.passphrase,
            }
        )

        # construct a new websocket session
        session = aiohttp.ClientSession()

        # connect to the websocket
        async with session.ws_connect(self.ws_url) as ws:
            # send the subscription  
            await ws.send_str(json.dumps(subscription))

            # for each message returned
            async for msg in ws:
                # only handle text message
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # load the data as json
                    x = json.loads(msg.data)

                    # ignore subscription  and heartbeat messages
                    if x["type"] in ("subscriptions", "heartbeat"):
                        # TODO yield heartbeats?
                        continue

                    elif x["type"] == "snapshot":
                        # maintain order book internally
                        # TODO
                        ...

                    elif x["type"] == "l2update":
                        # maintain order book internally
                        # TODO
                        ...

                    elif x["type"] == "ticker":
                        # maintain order book internally
                        # TODO
                        t = self._process_ticker(x)
                        e = Event(type=EventType.TRADE, target=t)
                        yield e

    async def websocket_trades(self, subscriptions: List[Instrument]):
        # copy the base subscription template
        subscription = _SUBSCRIPTION.copy()

        # get trades
        cast(List, subscription["channels"]).append("ticker")

        # for each subcription, add symbol to product_ids
        for sub in subscriptions:
            cast(List, subscription["product_ids"]).append(sub.brokerId)

        # sign the message in a similar way to the rest api, but
        # using the message of GET/users/self/verify
        timestamp = str(time.time())
        message = timestamp + "GET/users/self/verify"
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode(), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode()

        # update the subscription message with the signing info
        subscription.update(
            {
                "signature": signature_b64,
                "timestamp": timestamp,
                "key": self.api_key,
                "passphrase": self.passphrase,
            }
        )

        # construct a new websocket session
        session = aiohttp.ClientSession()

        async with session.ws_connect(self.ws_url) as ws:
            # send the subscription
            await ws.send_str(json.dumps(subscription))
            
            # for each message returned
            async for msg in ws:
                 # only handle text messages
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # load the data as json
                    x = json.loads(msg.data)

                    # ignore subscription  and heartbeat messages
                    if x["type"] in ("subscriptions", "heartbeat"):
                        # TODO yield heartbeats?
                        continue

                    elif x["type"] == "ticker":
                        t = self._process_ticker(x)
                        e = Event(type=EventType.TRADE, target=t)
                        yield e

    def _process_ticker(self, x: Dict[str, Union[str, int, float]]) -> Trade:
        o = Order(
            float(x["last_size"]) * self._multiple,
            float(x["price"]),
            Side(str(x["side"]).upper()),
            Instrument(str(x["product_id"]), InstrumentType.PAIR, self.exchange),
            self.exchange,
            filled=float(x["last_size"]) * self._multiple
        )

        t = Trade(
            float(x["last_size"]) * self._multiple,
            float(x["price"]),
            o
        )
        return t

    def _process_snapshot(self) -> None:
        # TODO
        pass

    def _process_l2update(self) -> None:
        # TODO
        pass

    def _process_open(self, x: Dict[str, Union[str, int, float]]) -> Order:
        # The order is now open on the order book.
        # This message will only be sent for orders
        # which are not fully filled immediately.
        # remaining_size will indicate how much of
        # the order is unfilled and going on the book.
        # {
        #     "type": "open",
        #     "time": "2014-11-07T08:19:27.028459Z",
        #     "product_id": "BTC-USD",
        #     "sequence": 10,
        #     "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
        #     "price": "200.2",
        #     "remaining_size": "1.00",
        #     "side": "sell"
        # }

        o = Order(
            float(x["remaining_size"]) * self._multiple,
            float(x["price"]),
            Side(str(x["side"]).upper()),
            Instrument(str(x["product_id"]), InstrumentType.PAIR, self.exchange),
            self.exchange,
        )
        return o

    def _process_match(self, x: Dict[str, Union[str, int, float]]) -> Trade:
        if str(x.get("taker_order_id", "")) in self._order_map:
            o = self._order_map[str(x.get("taker_order_id"))]

            o.filled = float(x["size"]) * self._multiple

            # my order
            mine = True

        elif str(x.get("maker_order_id", "")) in self._order_map:
            o = self._order_map[str(x.get("maker_order_id"))]
            # TODO filled?

            # my order
            mine = True

        else:
            o = Order(
                float(x["size"]) * self._multiple,
                float(x["price"]),
                Side(str(x["side"]).upper()),
                Instrument(str(x["product_id"]), InstrumentType.PAIR, self.exchange),
                self.exchange,
                filled=float(x["size"]) * self._multiple,
            )

            # not my order
            mine = False

        # create a trader with this order as the taker
        # makers would be accumulated via the
        # `elif x['reason'] == 'filled'` block above
        t = Trade(
            float(x["size"]) * self._multiple,
            float(x["price"]),
            taker_order=o,
            maker_orders=[],
        )

        if mine:
            t.my_order = o

        return t

    def _process_done(self, x: Dict[str, Union[str, int, float]]) -> Optional[Order]:
        # The order is no longer on the order book. Sent for
        # all orders for which there was a received message.
        # This message can result from an order being canceled
        # or filled. There will be no more messages for this
        # order_id after a done message. remaining_size indicates
        # how much of the order went unfilled; this will
        # be 0 for filled orders.
        #
        # market orders will not have a remaining_size or price
        # field as they are never on the open order book at a
        # given price.
        #
        # {
        #     "type": "done",
        #     "time": "2014-11-07T08:19:27.028459Z",
        #     "product_id": "BTC-USD",
        #     "sequence": 10,
        #     "price": "200.2",
        #     "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
        #     "reason": "filled", // or "canceled"
        #     "side": "sell",
        #     "remaining_size": "0"
        # }
        if x["reason"] == "canceled":
            id = x["order_id"]

            # if cancelled
            if "price" not in x:
                # cancel this event if we have a full local order book
                # where we can determine the original order
                print("TODO: noprice")
                return None

            # FIXME don't use remaining_size, lookup original size in order book
            o = Order(
                float(x["remaining_size"]) * self._multiple,
                float(x["price"]),
                Side(str(x["side"]).upper()),
                Instrument(
                    str(x["product_id"]),
                    InstrumentType.PAIR,
                    self.exchange,
                ),
                self.exchange,
                id=id,
            )
            return o

        elif x["reason"] == "filled":
            # Will have a match event
            # TODO route these to full local order book
            return None

        else:
            # TODO unhandled
            # this should never print
            print("TODO: unhandled", x)
        return None

    def _process_received(
        self, x: Dict[str, Union[str, int, float]]
    ) -> Optional[Order]:
        # generate new Open events
        # A valid order has been received and is now active.
        # This message is emitted for every single valid order as
        # soon as the matching engine receives it whether it fills
        # immediately or not.
        #
        # The received message does not indicate a resting order on
        # the order book. It simply indicates a new incoming order
        # which as been accepted by the matching engine for processing.
        # Received orders may cause match message to follow if they
        # are able to begin being filled (taker behavior). Self-trade
        # prevention may also trigger change messages to follow if the
        # order size needs to be adjusted. Orders which are not fully
        # filled or canceled due to self-trade prevention result in an
        # open message and become resting orders on the order book.
        #
        # Market orders (indicated by the order_type field) may have
        # an optional funds field which indicates how much quote currency
        # will be used to buy or sell. For example, a funds field of
        # 100.00 for the BTC-USD product would indicate a purchase of
        # up to 100.00 USD worth of bitcoin.
        #
        # {
        #     "type": "received",
        #     "time": "2014-11-07T08:19:27.028459Z",
        #     "product_id": "BTC-USD",
        #     "sequence": 10,
        #     "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
        #     "size": "1.34",
        #     "price": "502.1",
        #     "side": "buy",
        #     "order_type": "limit"
        # }
        # {
        #     "type": "received",
        #     "time": "2014-11-09T08:19:27.028459Z",
        #     "product_id": "BTC-USD",
        #     "sequence": 12,
        #     "order_id": "dddec984-77a8-460a-b958-66f114b0de9b",
        #     "funds": "3000.234",
        #     "side": "buy",
        #     "order_type": "market"
        # }
        id = x["order_id"]

        # FIXME make sure we dont need this
        # if id in self._order_map:
        #     # yield a received event and get order from dict
        #     o = self._order_map[id]
        #     yield Event(type=EventType.RECEIVED, target=o)

        if x["order_type"] == "market":
            if "size" in x and float(x["size"]) <= 0:
                # ignore zero size orders
                # TODO why do we even get these?
                return None

            elif "size" not in x and "funds" in x:
                print("TODO: funds")
                # TODO can't handle these yet, no mapping from funds to size/price
                return None

            # create a market data order from the event data
            # TODO set something for price? float('inf') ?
            o = Order(
                float(x["size"]) * self._multiple,
                0.0,
                Side(str(x["side"]).upper()),
                Instrument(str(x["product_id"]), InstrumentType.PAIR, self.exchange),
                self.exchange,
                id=id,
            )

        else:
            # create limit order from the event data
            o = Order(
                float(x["size"]) * self._multiple,
                float(x["price"]),
                Side(str(x["side"]).upper()),
                Instrument(str(x["product_id"]), InstrumentType.PAIR, self.exchange),
                self.exchange,
            )
        return o

    def _process_change(self, x: Dict[str, Union[str, int, float]]) -> Optional[Order]:
        # An order has changed. This is the result
        # of self-trade prevention adjusting the
        # order size or available funds. Orders can
        # only decrease in size or funds. change
        # messages are sent anytime an order changes
        # in size; this includes resting orders (open)
        # as well as received but not yet open.
        # change messages are also sent when a new
        # market order goes through self trade prevention
        # and the funds for the market order have changed.
        # {
        #     "type": "change",
        #     "time": "2014-11-07T08:19:27.028459Z",
        #     "sequence": 80,
        #     "order_id": "ac928c66-ca53-498f-9c13-a110027a60e8",
        #     "product_id": "BTC-USD",
        #     "new_size": "5.23512",
        #     "old_size": "12.234412",
        #     "price": "400.23",
        #     "side": "sell"
        # }
        # {
        #     "type": "change",
        #     "time": "2014-11-07T08:19:27.028459Z",
        #     "sequence": 80,
        #     "order_id": "ac928c66-ca53-498f-9c13-a110027a60e8",
        #     "product_id": "BTC-USD",
        #     "new_funds": "5.23512",
        #     "old_funds": "12.234412",
        #     "price": "400.23",
        #     "side": "sell"
        # }
        ...
