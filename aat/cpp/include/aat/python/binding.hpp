#pragma once
#define AAT_PYTHON

#include <deque>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/stl_bind.h>
#include <pybind11/chrono.h>
#include <pybind11/functional.h>
#include <pybind11_json/pybind11_json.hpp>

#include <aat/common.hpp>
#include <aat/config/enums.hpp>
#include <aat/core/data/data.hpp>
#include <aat/core/data/event.hpp>
#include <aat/core/data/order.hpp>
#include <aat/core/data/trade.hpp>
#include <aat/core/position/account.hpp>
#include <aat/core/position/cash.hpp>
#include <aat/core/position/position.hpp>
#include <aat/core/order_book/order_book.hpp>

namespace py = pybind11;
using namespace aat::common;

PYBIND11_MODULE(binding, m) {
    
}