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

    
} // namespace core
} // namespace aat