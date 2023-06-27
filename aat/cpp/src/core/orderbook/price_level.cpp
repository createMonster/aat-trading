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
    
} // namespace core
} // namespace aat