from collections import deque
from typing import Any, Callable, Deque, Optional, Type, TYPE_CHECKING

from aat.core.data import Event, Trade, Order
from aat.config import EventType

from ..cpp import _CPP, _make_cpp_collector


if TYPE_CHECKING:
    from ..price_level import _PriceLevel

class _Collector(object):
    __slots__ = [
        "_callback",
        "_event_queue",
        "_orders",
        "_taker_order",
        "_price_levels",
        "_price",
        "_volume",
    ]

    def __new__(cls: Type, *args: Any, **kwargs: Any) -> "_Collector":
        if _CPP:
            return _make_cpp_collector(*args, **kwargs)
        
        return super(_Collector, cls).__new__(cls)

    def __init__(self, callback: Callable = lambda *args: args) -> None:
        # callback to call to process events
        self._callback = callback

        # queue of events to trigger
        self._event_queue: Deque[Event] = deque()

        # queue of orders that are included in the trade
        self._orders: Deque[Order] = deque()

        # the taker order
        self._taker_order: Optional[Order] = None

        # pricelevels to clear, if we commit
        self._price_levels: Deque["_PriceLevel"] = deque()

        # reset status
        self.reset()
    
    