from abc import abstractmethod
from typing import List

from aat.core import ExchangeType, Instrument

from .base.market_data import _MarketData
from .base.order_entry import _OrderEntry


class Exchange(_MarketData, _OrderEntry):
    pass