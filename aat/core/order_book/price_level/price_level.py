from collections import deque
from typing import Any, cast, Deque, Dict, Iterator, Optional, List, Tuple, Type, Union

from aat.core.data import Order
from aat.config import OrderType, OrderFlag

from .ro import PriceLevelRO
from ..collector import _Collector
from ..cpp import _CPP, _make_cpp_price_level


class _PriceLevel(object):
    __slots__ = [
        "_price",
        "_orders",
        "_orders_staged",
        "_orders_filled_staged",
        "_stop_orders",
        "_stop_orders_staged",
        "_collector"
    ]
    
    def __new__(cls: Type, *args: Any, **kwargs: Any) -> "_PriceLevel":
        if _CPP:
            return _make_cpp_price_level(*args, **kwargs)
        
        return super(_PriceLevel, cls).__new__(cls)
    
    def __init__(self, price: float, collector: _Collector):
        self._price = price
        self._orders: Deque[Order] = deque()
        self._orders_staged: Deque[Order] = deque()
        self._orders_filled_staged: Deque[float] = deque()
        self._stop_orders: List[Order] = []
        self._stop_orders_staged: List[Order] = []
        self._collector = collector

    @property
    def price(self) -> float:
        return self._price
    
    @property
    def volume(self) -> float:
        return sum((x.volume - x.filled) for x in self._orders)
    
    def add(self, order: Order) -> None:
        # append order to deque
        if order.order_type == OrderType.STOP:
            if order.stop_target in self._stop_orders:
                return
            self._stop_orders.append(cast(Order, order.stop_target))

        else:
            if order in self._orders:
                # change event
                self._collector.pushChange(order)
            else:
                if order.filled < order.volume:
                    self._orders.append(order)
                    self._collector.pushOpen(order)

    def find(self, order: Order) -> Optional[Order]:
        # check if order is in level
        if order.price != self._price:
            # order not here anymore
            return None
        
        for o in self._orders:
            if o.id == order.id:
                return o
            
        return None

    def modify(self, order: Order) -> Order:
        # Check if order is in level
        if order.price != self._price or order.id not in (o.id for o in self._orders):
            # something is wrong
            raise Exception(f"Order not found in price level {self._price}: {order}")
        
        # modify order
        for o in self._orders:
            if o.id == order.id:
                # only allowed to modify volume
                o.volume = order.volume

        # trigger cancel event
        self._collector.pushChange(order)

    def remove(self, order: Order) -> Order:
        pass

    def cross(self, take_order: Order) -> Tuple[Optional[Order], List[Order]]:
        """
        Args:
            take_order(Order): The order that cross the spreads
        Returns:
            order(Order or None): the order crossing, if there is some remaining
            secondary orders (List[Order] or None): orders get triggered as a result of crossing (e.g. stop orders)
        """
        pass

    def clear():
        pass

    def _get_stop_orders():
        pass

    def commit():
        pass

    def revert():
        pass

    def __bool__(self):
        pass

    def __iter__(self):
        pass

    def __len__(self):
        pass

    def __getitem__(self):
        pass

    def ro():
        pass

    def toDict():
        pass
    
