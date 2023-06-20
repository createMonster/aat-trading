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


    ENUM_TO_STRING(TradingType)
    ENUM_TO_STRING(Side)
    ENUM_TO_STRING(OptionType)
    ENUM_TO_STRING(EventType)
    ENUM_TO_STRING(DataType)
    ENUM_TO_STRING(InstrumentType)
    ENUM_TO_STRING(OrderType)
    ENUM_TO_STRING(OrderFlag)

    ENUM_FROM_STRING(Side)
    ENUM_FROM_STRING(EventType)
    ENUM_FROM_STRING(DataType)
    ENUM_FROM_STRING(InstrumentType)
    ENUM_FROM_STRING(OrderType)
    ENUM_FROM_STRING(OrderFlag)
    ENUM_FROM_STRING(ExitRoutine)

} // namespace config
} // namespace aat