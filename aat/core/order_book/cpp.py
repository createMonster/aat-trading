from typing import Callable

from aat.common import _in_cpp
from aat.core import ExchangeType, Instrument


try:
    from aat.binding import OrderbookCpp
    from aat.binding import _CollectorCpp
    from aat.binding import _PricelevelCpp

    _CPP = _in_cpp()
except ImportError:
    OrderbookCpp, _CollectorCpp, _PricelevelCpp = object, object, object
    _CPP = False


def _make_cpp_orderbook(
    instrument: Instrument,
    exchange_name: str = "",
    callback: Callable = lambda x: print(x)
) -> OrderbookCpp:
    return OrderbookCpp(instrument, exchange_name or ExchangeType(""), callback)

def _make_cpp_collector(callback: Callable = lambda *args: args) -> _CollectorCpp:
    return _CollectorCpp(callback)

def _make_cpp_price_level(price: float, collector: _CollectorCpp) -> _PricelevelCpp:
    return _PricelevelCpp(price, collector)