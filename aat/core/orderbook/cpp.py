from typing import Callable

from aat.common import _in_cpp


try:
    from aat.binding import OrderbookCpp
    from aat.binding import _CollectorCpp
    from aat.binding import _PricelevelCpp

    _CPP = _in_cpp()
except ImportError:
    OrderbookCpp, _CollectorCpp, _PricelevelCpp = object, object, object


def _make_cpp_orderbook():
    pass

def _make_cpp_collector():
    pass

def _make_cpp_price_level():
    pass