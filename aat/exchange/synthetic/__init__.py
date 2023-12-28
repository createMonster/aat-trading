import asyncio
import numpy as np
import string
from datetime import datetime, timedelta
from collections import deque
from random import choice, random, randint
from typing import Optional, AsyncIterator, Deque, Iterator, List, Set

from aat.core import ExchangeType
from ..exchange import Exchange
from ...core import Instrument, OrderBook, Order, Event, ExchangeType, Position
from ...config import TradingType, Side, EventType, OrderType

def _getName(n: int = 1) -> List[str]:
    columns = [
        "".join(np.random.choice(list(string.ascii_uppercase), choice((1, 2, 3, 4))))
        + "."
        + "".join(np.random.choice(list(string.ascii_uppercase), choice((1, 2))))
        for _ in range(n)
    ]
    return columns

class SynthethicExchange(Exchange):
    _inst = 0

    def __init__(
        self,
        trading_type: Optional[TradingType] = None,
        verbose: bool = False,
        inst_count: int = 3,
        cycles: int = 10000,
        positions: bool = False,
    ) -> None:
        """A synthetic exchange. Runs a limit order book for a number of randomly generated assets,
        takes random walks.

        Args:
            trading_type (TradingType); Trading type. Should be in (SIMULATION, BACKTEST)
            verbose (bool); run in verbose mode (prints order books every tick)
            inst_count (int); number of random instruments to use
            cycles (int); number of random cycles to go through, each cycle
                          it will randomly generate an order event.
            positions (bool); randomly generate starting positions
        """
        super().__init__(ExchangeType("synthetic{}".format(SynthethicExchange._inst)))
        print("using synthetic exchange: {}".format(self.exchange()))

        if trading_type not in (TradingType.SIMULATION, TradingType.BACKTEST):
            raise Exception("Invalid trading type: {}".format(trading_type))
        self._trading_type = trading_type
        self._verbose = verbose
        self._sleep = (
            0.3
            if trading_type
            in (TradingType.LIVE, TradingType.SIMULATION, TradingType.SANDBOX)
            else 0.0
        )