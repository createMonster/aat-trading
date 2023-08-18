from queue import Queue
from typing import (
    Any,
    Callable,
    cast,
    Iterator,
    List,
    Dict,
    Optional,
    Tuple,
    Type,
    Union,
)

from aat.core import ExchangeType, Order, Instrument, Event
from aat.config import Side, OrderFlag, OrderType

from ..base import OrderBookBase
from ..cpp import _CPP, _make_cpp_orderbook
from ..collector import _Collector
from ..price_level import _PriceLevel, PriceLevelRO
from ..utils import _insort
