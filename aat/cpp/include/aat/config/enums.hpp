#pragma once

#include <iostream>
#include <unordered_map>
#include <vector>

#include <aat/common.hpp>

using namespace aat::common;

namespace aat {
namespace config {

    enum class TradingType {
        LIVE = 0,
        SIMIULATION = 1,
        SANDBOX = 2,
        BACKTEST = 3,
    };
    
    enum class Side {
        NONE = 0,
        BUY = 1,
        SELL = 2,
    };

    enum class OptionType {
        CALL = 0,
        PUT = 1,
    };

    
} // namespace config
} // namespace aat