import os
from typing import List, AsyncGenerator, Any

from aat.core import ExchangeType, Order, Instrument, Position, Event
from aat.config import TradingType, InstrumentType
from aat.exchange import Exchange

from .client import CoinbaseExchangeClient

class CoinbaseProExchange(Exchange):
    """Coinbase Pro Exchange

    Args:
        trading_type (TradingType): type of trading to do. Must be Sandbox or Live
        verbose (bool): run in verbose mode
        api_key (str): Coinbase API key
        api_secret (str): Coinbase API secret
        api_passphrase (str): Coinbase API passphrase
        order_book_level (str): Level of orderbook to trace, must be 'l3', 'l2', or 'trades'
    """

    def __init__(
        self, 
        trading_type: TradingType,
        verbose: bool,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
        order_book_level: str = "trades",
        satoshis: bool = False,
        **kwargs: dict
    ) -> None:
        self._trading_type = trading_type
        self._verbose = verbose

        # coinbase keys
        self._api_key = api_key or os.getenv("API_KEY", "")
        self._api_secret = api_secret or os.getenv("API_SECRET", "")
        self._api_passphrase = api_passphrase or os.getenv("API_PASSPHRASE", "")

        # orderbook level to track
        if order_book_level not in ("l3", "l2", "trades"):
            raise NotImplementedError("`order_book_level` must be in (l3, l2, trades)")
        self._order_book_level = order_book_level

        # enforce authentication
        if not (self._api_key and self._api_secret and self._api_passphrase):
            raise Exception("No coinbase auth!")

        # don't implement backtest for now
        if trading_type == TradingType.BACKTEST:
            raise NotImplementedError()
        
        # don't implement simulation for now
        if trading_type == TradingType.SIMULATION:
            raise NotImplementedError()
        
        if self._trading_type == TradingType.SANDBOX:
            # coinbase sandbox
            super().__init__(ExchangeType("coinbaseprosandbox"))

        else:
            # Coinbase live trading
            print("*" * 100)
            print("*" * 100)
            print("WARNING: LIVE TRADING")
            print("*" * 100)
            print("*" * 100)
            super().__init__(ExchangeType("coinbasepro"))

        # multiply by 100,000,000 and do everything in integer volumes
        self._satoshis = satoshis
        
        self._client = CoinbaseExchangeClient(
            self._trading_type,
            self.exchange(),
            self._api_key,
            self._api_secret,
            self._api_passphrase,
            self._satoshis,
        )
        
        # list of market data subscriptions
        self._subscriptions: List[Instrument] = []

    async def connect(self) -> None:
        """connect to exchange, should be asynchronous"""
        self._client.instruments()
