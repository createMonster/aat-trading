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
from aat.core.data import Order

from ..base import OrderBookBase
from ..cpp import _CPP, _make_cpp_orderbook
from ..collector import _Collector
from ..price_level import _PriceLevel, PriceLevelRO
from ..utils import _insort


class OrderBook(OrderBookBase):
    """
    Args:
        instrument: The instrument of the book
        exchange_name: The name of the exchange
        callback(Function): callback on events
    """

    def __new__(cls: Type, *args: Any, **kwargs: Any) -> "OrderBook":
        if _CPP:
            return _make_cpp_orderbook(*args, **kwargs)
        return super(OrderBook, cls).__new__(cls)
    
    def __init__(self,
                 instrument: Instrument,
                 exchange_name: Union[ExchangeType, str] = "",
                 callback: Optional[callable] = None) -> None:
        self._instrument = instrument
        self._exchange_name = (
            exchange_name if isinstance(exchange_name, ExchangeType)
            else ExchangeType(exchange_name or "")
        )
        self._callback = callback

        # reset levels and collectors
        self.reset()
        
        # default callback is to enqueue
        self._queue: Queue[Event] = Queue()

    @property
    def instrument(self) -> Instrument:
        return self._instrument

    @property
    def exchange(self) -> ExchangeType:
        return self._exchange_name

    @property
    def callback(self) -> Callable:
        return self._callback

    @property
    def queue(self) -> Queue:
        return self._queue
    
    def _push(self, event: Event) -> None:
        self._queue.put(event)

    def reset(self) -> None:
        """
        Reset the orderbook to its base state
        """
        # levels look like [10, 10.5, 11, 11.5]
        self._buy_levels: List[float] = []
        self._sell_levels: List[float] = []

        # look like {price level: PriceLevel}
        self._buys: Dict[float, _PriceLevel] = {}
        self._sells: Dict[float, _PriceLevel] = {}
        
        # setup collector for conditional orders
        self._collector = _Collector(self._callback)

    def setCallback(self, callback: Callable) -> None:
        self._callback = callback
        self._collector.setCallback(callback)

    def find(self, order: Order) -> Optional[Order]:
        """find an order in the order book
        Args:
            order (Data): order to find in orderbook
        """

        price = order.price
        side = order.side
        levels = self._buy_levels if side == Side.BUY else self._sell_levels
        prices = self._buys if side == Side.BUY else self._sells

        if price not in levels:
            return None
        
        # find order from pricelevel
        return prices[price].find(order)
    
    def topOfBook(self) -> Dict[Side, PriceLevelRO]:
        """return top of both sides

        Args:

        Returns:
            value (dict): returns {BUY: tuple, SELL: tuple}
        """

        return {
            Side.BUY: cast(PriceLevelRO, self.bids(levels=0)),
            Side.SELL: cast(PriceLevelRO, self.asks(levels=0)),
        }

    def spread(self) -> float:
        """return the spread

        Args:

        Returns:
            value (float): spread between bid and ask
        """
        tob: Dict[Side, PriceLevelRO] = self.topOfBook()
        return tob[Side.BUY] - tob[Side.SELL]
    
    def level(self, level: int = 0, price: Optional[float] = None) -> Tuple:
        """return book level

        Args:
            level (int): depth of book to return
            price (float): price level to look for
        Returns:
            value (tuple): returns ask, bid
        """
        # collect bids and asks at `level`
        if price:
            return (
                PriceLevelRO(
                    self._sells[price].price,
                    self._sells[price].volume,
                    len(self._sells[price])
                )
                if price in self._sell_levels
                else None,
                PriceLevelRO(
                    self._buys[price].price,
                    self._buys[price].volume,
                    len(self._buys[price])
                )
                if price in self._buy_levels
                else None
            )
        
        return (
            PriceLevelRO(
                self._sell_levels[level],
                self._sells[self._sell_levels[level]].volume,
                len(self._sells[self._sell_levels[level]]),
                self._sells[self._sell_levels[level]]._orders
            )
            if len(self._sell_levels) > level
            else PriceLevelRO(0.0, 0.0, 0),
            PriceLevelRO(
                self._buy_levels[-level - 1],
                self._buys[self._buy_levels[-level - 1]].volume,
                len(self._buys[self._buy_levels[-level - 1]]),
                self._buys[self._buy_levels[-level - 1]]._orders,
            )
            if len(self._buy_levels) > level
            else PriceLevelRO(0.0, 0.0, 0),
        )
            
        
    def bids(
        self, levels: int = 0
    ) -> Union[PriceLevelRO, List[Optional[PriceLevelRO]]]:
        """return bid levels starting at top

        Args:
            levels (int): number of levels to return
        Returns:
            value (dict of list): returns [levels in order] for `levels` number of levels
        """
        if levels <= 0:
            return (
                PriceLevelRO(
                    self._buy_levels[-1],
                    self._buys[self._buy_levels[-1]].volume,
                    len(self._buys[self._buy_levels[-1]]),
                    self._buys[self._buy_levels[-1]]._orders,
                )
                if len(self._buy_levels) > 0
                else PriceLevelRO(0, 0, 0)
            )
        return [
            PriceLevelRO(
                self._buy_levels[-i - 1],
                self._buys[self._buy_levels[-i - 1]].volume,
                len(self._buys[self._buy_levels[-i - 1]]),
                self._buys[self._buy_levels[-i - 1]]._orders,
            )
            if len(self._buy_levels) > i
            else None
            for i in range(levels)
        ]

    def asks(
        self, levels: int = 0
    ) -> Union[PriceLevelRO, List[Optional[PriceLevelRO]]]:
        """return ask levels starting at top

        Args:
            levels (int): number of levels to return
        Returns:
            value (dict of list): returns [levels in order] for `levels` number of levels
        """
        if levels <= 0:
            return (
                PriceLevelRO(
                    self._sell_levels[0],
                    self._sells[self._sell_levels[0]].volume,
                    len(self._sells[self._sell_levels[0]]),
                    self._sells[self._sell_levels[0]]._orders,
                )
                if len(self._sell_levels) > 0
                else PriceLevelRO(float("inf"), 0, 0)
            )
        return [
            PriceLevelRO(
                self._sell_levels[i],
                self._sells[self._sell_levels[i]].volume,
                len(self._sells[self._sell_levels[i]]),
                self._sells[self._sell_levels[i]]._orders,
            )
            if len(self._sell_levels) > i
            else None
            for i in range(levels)
        ]
    
    def levels():
        pass

    def cancel():
        pass

    def _clearOrders():
        pass

    def _getTop():
        pass

    


        