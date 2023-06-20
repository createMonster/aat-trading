#include <aat/common.hpp>
#include <aat/core/order_book/collector.hpp>

using namespace aat::common;

namespace aat {
namespace core {
    Collector::Collector()
        : callback(nullptr)
        , price(0.0)
        , volume(0.0) {}
    
} // namespace core
} // namespace aat
