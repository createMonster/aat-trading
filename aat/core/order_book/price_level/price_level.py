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
        # Check if order is in level
        if order.price != self._price or order.id not in (o.id for o in self._orders):
            # something is wrong
            raise Exception(f"Order not found in price level {self._price}: {order}")
        
        # remove the order
        self._orders.remove(order)
        
        # push cancel event
        self._collector.pushCancel(order)

        return order

    def cross(self, take_order: Order) -> Tuple[Optional[Order], List[Order]]:
        """
        Args:
            take_order(Order): The order that cross the spreads
        Returns:
            order(Order or None): the order crossing, if there is some remaining
            secondary orders (List[Order] or None): orders get triggered as a result of crossing (e.g. stop orders)
        """
        if take_order.order_type == OrderType.STOP:
            self.add(take_order)
            return None, []
        
        if take_order.filled == take_order.volume:
            # already filled
            return None, self._get_stop_orders()
        
        elif take_order.filled > take_order.volume:
            raise Exception("Unknown error occurred - order book is corrupt")
        
        while (take_order.filled < take_order.volume) and self._orders:
            # need to fill original volume - filled so far
            to_fill = take_order.volume - take_order.filled
            
            # pop maker order from list
            maker_order = self._orders.popleft()

            # add to staged in case we need to revert
            self._orders_staged.append(maker_order)

            # remaining in maker order
            maker_remaining = maker_order.volume - maker_order.filled

            if maker_remaining > to_fill:
                # handle fill or kill / all or nothing
                if maker_order.flag in (OrderFlag.FILL_OR_KILL, OrderFlag.ALL_OR_NONE):
                    # kill the maker order and continue
                    self._collector.pushCancel(maker_order)

                    # won't fill anything from that order
                    self._orders_filled_staged.append(0.0)
                    continue
                else:
                    # maker order is partially executed
                    maker_order.filled += to_fill
                    
                    # will exit loop
                    take_order.filled = take_order.volume
                    self._collector.pushFill(take_order)

                    # change event
                    self._collector.pushChange(maker_order, True, to_fill)

                    if maker_order.flag == OrderFlag.IMMEDIATE_OR_CANCEL:
                        # cancel maker event, don't put in queue
                        self._collector.pushCancel(maker_order)
                    else:
                        # push back in deque
                        self._orders.appendleft(maker_order)

            elif maker_remaining < to_fill:
                pass
            else:
                pass

    def clear(self) -> None:
        """clear queues"""
        pass

    def _get_stop_orders():
        pass

    def commit(self) -> None:
        """staged orders accepted, clear"""
        self.clear()

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
    
