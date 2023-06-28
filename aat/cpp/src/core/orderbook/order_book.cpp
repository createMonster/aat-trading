#include <aat/core/order_book/order_book.hpp>

namespace aat {
namespace core {
    
    OrderBookIterator&
    OrderBookIterator::operator++() {
        // TODO

        return *this;
    }

    std::shared_ptr<Order>
    OrderBookIterator::operator*() {
        if (side == Side::SELL) {
            return (*(order_book.sells.at(price_level)))[index_in_level];
        }
        else {
            return (*(order_book.buys.at(price_level)))[index_in_level];
        }
    }

    bool 
    OrderBookIterator::operator==(const OrderBookIterator &that) {
        //TODO
        return false;
    }

    OrderBook::OrderBook(const Instrument &instrument)
        : instrument(instrument)
        , exchange(NullExchange)
        , callback(nullptr) {}

    OrderBook::OrderBook(const Instrument &instrument, const ExchangeType &exchange)
        : instrument(instrument)
        , exchange(exchange)
        , callback(nullptr) {}

    OrderBook::OrderBook(
        const Instrument& instrument, const ExchangeType& exchange, std::function<void(std::shared_ptr<Event>)> callback)
        : instrument(instrument)
        , exchange(exchange)
        , callback(callback) {}

    void 
    OrderBook::setCallback(std::function<void(std::shared_ptr<Event>)> callback){
        collector.setCallback(callback);
    }

    void 
    OrderBook::reset() {
        buy_levels = std::vector<double>();
        sell_levels = std::vector<double>();
        buys = std::unordered_map<double, std::shared_ptr<PriceLevel>>();
        sells = std::unordered_map<double, std::shared_ptr<PriceLevel>>();
        collector = Collector(callback);
    }

    void 
    OrderBook::add(std::shared_ptr<Order> order) {
        // secondary triggered orders
        std::vector<std::shared_ptr<Order>> secondaries;
        
        // order is buy, look at top of sell side
        double top = getTop(order->side, collector.getClearedLevels());
        
        //set levels to the right side
        std::vector<double> &levels = (order->side == Side::BUY) ? buy_levels : sell_levels;
        std::unordered_map<double, std::shared_ptr<PriceLevel>> &prices = (order->side == Side::BUY) ? buys : sells;
        std::unordered_map<double, std::shared_ptr<PriceLevel>> &prices_cross = (order->side == Side::BUY) ? sells : buys;

        // set order price appropriately
        double order_price;
        if (order->order_type == OrderType::MARKET) {
            if (order->flag == OrderFlag::NONE) {
                // price goes infinite "fill however you want"
                order_price = 
                    (order->side == Side::BUY) ? std::numeric_limits<double>::max() : std::numeric_limits<double>::min();
            }
            else {
                // with a flag, it will have a price
                order_price = order->price;
            }
        }
        else {
            order_price = order->price;
        }
        
        // Check if crosses
        while (top > 0.0 && ((order->side == Side::BUY) ? order_price >= top : order_price <= top)) {
            // execute order against level
            // if returns trade, it cleared the level
            // else, order was fully executed
            std::shared_ptr<Order> trade = prices_cross[top]->cross(order, secondaries);
            if (trade) {
                // clear sell level
                top = getTop(order->side, collector.clearLevel(prices_cross[top]));
                continue;
            }

            // trade is done, check if level was cleared exactly
            if (prices_cross.at(top)->size() <= 0) {
                //level cleared exactly
                collector.clearLevel(prices_cross.at(top));
            }
            break;
        }

        // if order remaining, check rules / push to book
        
        
    }





    

    double
    OrderBook::getTop(Side side, uint_t cleared) {
        if (side == Side::BUY) {
            if (sell_levels.size() > cleared) {
                return sell_levels[cleared];
            }
            else {
                return -1;
            }
        }
        else {
            if (buy_levels.size() > cleared) {
                return buy_levels[buy_levels.size()-cleared-1];
            }
            else {
                return -1;
            }
        }
    }
    
} // namespace core
} // namespace aat