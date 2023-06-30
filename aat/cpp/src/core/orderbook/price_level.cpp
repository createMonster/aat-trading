#include <aat/core/order_book/price_level.hpp>

using namespace aat::common;
using namespace aat::config;

namespace aat {
namespace core {
    
    PriceLevel::PriceLevel(double price, Collector &collector)
        : price(price)
        , collector(collector)
        , orders()
        , orders_staged()
        , stop_orders()
        , stop_orders_staged() {}

    double
    PriceLevel::getVolume() const {
        double sum = 0.0;
        for (std::shared_ptr<Order> order: orders) {
            sum += (order->volume - order->filled);
        }
        return sum;
    }
    
    void
    PriceLevel::add(std::shared_ptr<Order> order) {
        // append order to deque
        if (order->order_type == OrderType::STOP) {
            if (orders.size() > 0 && std::find(orders.begin(), orders.end(), order->stop_target) != orders.end()) {
                return;
            }
            stop_orders.push_back(order->stop_target);
        } else {
            if (orders.size() > 0 && std::find(orders.begin(), orders.end(), order) != orders.end()) {
                collector.pushChange(order);
            } else {
                // change event
                orders.push_back(order);
                collector.pushOpen(order);
            }
        }
    
    }

    std::shared_ptr<Order> 
    PriceLevel::find(std::shared_ptr<Order> order) {
        // check if order is in level
        if (order->price != price) {
            return nullptr;
        }
        
        for (auto o : orders) {
            if (o->id == order->id) {
                return o;
            }
        }
        return nullptr;
    }

    std::shared_ptr<Order> 
    PriceLevel::modify(std::shared_ptr<Order> order) {
        // check if order in level
        if (order->price != price || std::find(orders.begin(), orders.end(), order) == orders.end()) {
            // something is wrong
            throw AATCPPException("Order not found in price level");
        }

        // remove order
        orders.erase(std::find(orders.begin(), orders.end(), order));
        
        // trigger change event
        collector.pushChange(order);
        
        return order;
    }

    std::shared_ptr<Order> 
    PriceLevel::remove(std::shared_ptr<Order> order) {
        // check if order in level
        if (order->price != price || std::find(orders.begin(), orders.end(), order) == orders.end()) {
            // something is wrong
            throw AATCPPException("Order not found in price level");
        }

        // remove order
        orders.erase(std::find(orders.begin(), orders.end(), order));
        
        // trigger change event
        collector.pushCancel(order);
        
        return order;
    }

    std::shared_ptr<Order>
    PriceLevel::cross(std::shared_ptr<Order> taker_order, std::vector<std::shared_ptr<Order>> &secondaries) {
        if (taker_order->order_type == OrderType::STOP) {
            add(taker_order);
            return nullptr;
        }
        
        if (taker_order->filled == taker_order->volume) {
            // already filled
            for (std::shared_ptr<Order> order : stop_orders)
                secondaries.push_back(order);
            return nullptr;
        }
        else if (taker_order->filled > taker_order->volume) {
            throw AATCPPException("Unknown error occured - order book is corrupt");
        }

        while (taker_order->filled < taker_order->volume && orders.size() > 0) {
            // need to fill original volume - filled
            double to_fill = taker_order->volume - taker_order->filled;
            
            // pop maker order from list
            std::shared_ptr<Order> maker_order = orders.front();
            orders.pop_front();
            
            // Add to staged in case we need to revert
            orders_staged.push_back(maker_order);
            
            // remaining in makerd_order
            double maker_remaining = maker_order->volume - maker_order->filled;
            if (maker_remaining > to_fill) {
                // handle fill or kill / all or nothing
                if (maker_order->flag == OrderFlag::FILL_OR_KILL || maker_order->flag == OrderFlag::ALL_OR_NONE) {
                    // kill the maker order and continue
                    collector.pushCancel(maker_order);

                    // won't fill anything from that order
                    orders_filled_staged.push_back(0.0);

                    continue;
                }
                else {
                    // maker order is partially executed
                    maker_order->filled += to_fill;

                    // won't fill anything from that order
                    orders_filled_staged.push_back(to_fill);
                    
                    // will exit loop
                    taker_order->filled = taker_order->volume;
                    collector.pushFill(taker_order);
                    
                    // change event
                    collector.pushChange(maker_order, true, to_fill);
                }
            }
            else if (maker_remaining < to_fill) {
                // partially fill it regardless
                // this will either trigger the revert in order_book,
                // or it will be partially executed
                taker_order->filled += maker_remaining;
                if (taker_order->flag == OrderFlag::ALL_OR_NONE) {
                    // taker order cannot be filled, push maker back and cancel taker
                    // push back in deque
                    orders.push_front(maker_order);
                    for (std::shared_ptr<Order> order : stop_orders) {
                        secondaries.push_back(order);
                    }
                    return nullptr;
                }
                else {
                    // maker_order is fully execulted
                    maker_order->filled = maker_order->volume;
                    
                    // append filled in case need to revert
                    orders_filled_staged.push_back(maker_order->volume);

                    // don't append to deque
                    // tell maker order filled
                    collector.pushChange(taker_order);
                    collector.pushFill(maker_order, true, maker_remaining);
                }
            }
            else {
                // extactly equal
                maker_order->filled += to_fill;
                taker_order->filled += maker_remaining;
                
                // won't fill anything from that order
                orders_filled_staged.push_back(to_fill);
                
                collector.pushFill(taker_order);
                collector.pushFill(maker_order, true, to_fill);
            }
        }
        
        if (taker_order->filled == taker_order->volume) {
            // execute taker order
            collector.pushTrade(taker_order, taker_order->filled);
            
            // return nothing to signify to stop
            for (std::shared_ptr<Order> order : stop_orders) {
                secondaries.push_back(order);
            }
            return nullptr;
        } else if (taker_order->filled > taker_order->volume) {
            throw AATCPPException("Unknown error occurred - order book is corrupt");
        }

        // return order, this level is cleared and the order still has volume
        for (std::shared_ptr<Order> order : stop_orders) {
            secondaries.push_back(order);
        }
        return taker_order;
    }
    
    
    
    
} // namespace core
} // namespace aat