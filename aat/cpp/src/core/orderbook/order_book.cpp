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
        if (side = Side::SELL) {
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
        
    }
    
} // namespace core
} // namespace aat