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
        if (order->filled < order->volume) {
            if (order->order_type == OrderType::MARKET) {
                // market orders
                if (order->flag == OrderFlag::ALL_OR_NONE || order->flag == OrderFlag::FILL_OR_KILL) {
                    // cancel the order, do not execute any
                    collector.revert();
                    
                    // cancel the order
                    collector.pushCancel(order);
                    collector.commit();
                } else {
                    // market order, partial
                    if (order->filled > 0)
                        collector.pushTrade(order, order->filled);
                    
                    // clear levels
                    clearOrders(order, collector.getClearedLevels());
                    
                    // execute order
                    collector.pushCancel(order);
                    collector.commit();
                    
                    // execute secondaries
                    for (std::shared_ptr<Order> secondary : secondaries) {
                        secondary->timestamp = order->timestamp;
                        add(secondary);
                    }
                }
            } else {
                // limit orders
                if (order->flag == OrderFlag::FILL_OR_KILL) {
                    if (order->filled > 0) {
                        // reverse partial, canncel the order, do not execute any
                        collector.revert();
                        //cancel the order
                        collector.pushCancel(order);
                        collector.commit();
                    } else {
                        // add to book
                        collector.commit();

                        // limit order, put on books
                        if (insort(levels, order->price)) {
                            // new price level
                            prices[order->price] = std::make_shared<PriceLevel>(order->price, collector);
                        }
                        
                        // add order to price level
                        prices[order->price]->add(order);

                        // execute secondaries
                        for (std::shared_ptr<Order> secondary : secondaries) {
                            secondary->timestamp = order->timestamp;
                            add(secondary);
                        }
                    }
                } else if (order->flag == OrderFlag::ALL_OR_NONE) {
                    if (order->filled > 0) {
                        // order could not fill fully, revert
                        // cancel the order, do not execute any
                        collector.revert();
                        collector.pushCancel(order);
                        collector.commit();
                    } else {
                        // add to book
                        collector.commit();

                        // limit order, put on books
                        if (insort(levels, order->price)) {
                            // new price level
                            prices[order->price] = std::make_shared<PriceLevel>(order->price, collector);
                        }
                        
                        // add order to price level
                        prices[order->price]->add(order);

                        // execute secondaries
                        for (std::shared_ptr<Order> secondary : secondaries) {
                            secondary->timestamp = order->timestamp;
                            add(secondary);
                        }
                    }
                } else if (order->flag == OrderFlag::IMMEDIATE_OR_CANCEL) {
                    if (order->filled > 0) {
                        // clear levels
                        clearOrders(order, collector.getClearedLevels());

                        // execute the ones that filled, kill the remainder
                        collector.pushCancel(order);
                        collector.commit();

                        // execute secondaries
                        for (std::shared_ptr<Order> secondary : secondaries) {
                        secondary->timestamp = order->timestamp;  // adjust trigger time
                        add(secondary);
                        }

                    } else {
                        // add to book
                        collector.commit();

                        // limit order, put on books
                        if (insort(levels, order->price)) {
                        // new price level
                        prices[order->price] = std::make_shared<PriceLevel>(order->price, collector);
                        }
                        // add order to price level
                        prices[order->price]->add(order);

                        // execute secondaries
                        for (std::shared_ptr<Order> secondary : secondaries) {
                        secondary->timestamp = order->timestamp;  // adjust trigger time
                        add(secondary);
                        }
                    }
                } else {
                    // clear levels
                    clearOrders(order, collector.getClearedLevels());

                    // execute order
                    collector.commit();

                    // limit order, put on books
                    if (insort(levels, order->price)) {
                        // new price level
                        prices[order->price] = std::make_shared<PriceLevel>(order->price, collector);
                    }

                    // add order to price level
                    prices[order->price]->add(order);

                    // execute secondaries
                    for (std::shared_ptr<Order> secondary : secondaries) {
                        secondary->timestamp = order->timestamp;  // adjust trigger time
                        add(secondary);
                    }
                }
            }
        } else {
            // don't need to add trade as this is done in the price_levels
            
            // clear levels
            clearOrders(order, collector.getClearedLevels());
            
            // execute all orders
            collector.commit();

            // execute secondaries
            for (std::shared_ptr<Order> secondary : secondaries) {
                secondary->timestamp = order->timestamp;
                add(secondary);
            }
        }
        
        // clear the collector
        collector.clear();
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