#pragma once
#include <deque>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include <unordered_map>

#include <aat/common.hpp>
#include <aat/core/order_book/price_level.hpp>
#include <aat/core/order_book/collector.hpp>
#include <aat/core/exchange/exchange.hpp>
#include <aat/core/data/event.hpp>
#include <aat/core/data/order.hpp>

using namespace aat::common;

namespace aat {
namespace core {

    class OrderBook;
    
    class OrderBookIterator {
        public:
            explicit OrderBookIterator(
                const OrderBook &book, double price_level = 0.0, int index_in_level = 0, Side side = Side::SELL)
                : order_book(book)
                , price_level(price_level)
                , index_in_level(index_in_level)
                , side(side) {}

            OrderBookIterator& operator++();
            std::shared_ptr<Order> operator*();
            bool operator==(const OrderBookIterator& that);

        private:
            const OrderBook &order_book;
            double price_level;
            int index_in_level;
            Side side;
    };

    class OrderBook {
        public:
            explicit OrderBook(const Instrument &instrument);
            OrderBook(const Instrument &instrument, const ExchangeType& exchange);
            OrderBook(
                const Instrument &instrument, const ExchangeType& exchange, std::function<void(std::shared_ptr<Event>)> callback
            );
            void setCallback(std::function<void(std::shared_ptr<Event>)> callback);

            Instrument 
            getInstrument() const {
                return instrument;
            }

            ExchangeType
            getExchange() const {
                return exchange;
            }

            std::function<void(std::shared_ptr<Event>)>
            getCallback() const {
                return callback;
            }

            void reset();
            void add(std::shared_ptr<Order> order);
            void cancel(std::shared_ptr<Order> order);
            void change(std::shared_ptr<Order> order);

            
            
    };
} // namespace core
} // namespace aat