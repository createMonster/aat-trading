#pragma once

#include <exception>
#include <stdint.h>
#include <string>
#include <sstream>
#include <cstdint>

#include <nlohmann/json.hpp>
#include <date.h>

using json = nlohmann::json;

#ifdef AAT_PYTHON
#include <pybind11/pybind11.h>
#define ENUM_TO_STRING(type)                                                                                           \
  inline std::string type##_to_string(type typ) { return type##_names[static_cast<int>(typ)]; }
#define ENUM_FROM_STRING(type)                                                                                         \
  type inline type##_from_string(char* s) {                                                                            \
    if (_##type##_mapping.find(s) == _##type##_mapping.end()) {                                                        \
      throw py::value_error(s);                                                                                        \
    }                                                                                                                  \
    return _##type##_mapping[s];                                                                                       \
  }
#else
#define ENUM_TO_STRING(type)                                                                                           \
  inline std::string type##_to_string(type typ) { return type##_names[static_cast<int>(typ)]; }
#define ENUM_FROM_STRING(type)                                                                                         \
  type inline type##_from_string(char* s) {                                                                            \
    if (_##type##_mapping.find(s) == _##type##_mapping.end()) {                                                        \
      throw AATCPPException(s);                                                                                        \
    }                                                                                                                  \
    return _##type##_mapping[s];                                                                                       \
  }
#endif


namespace aat {
namespace common {
    class AATCPPException : public std::exception {
        private: 
        std::string msg = "";

        public:
        explicit AATCPPException(std::string msg)
         : msg(msg) {}

        const char*
        what() const noexcept override {
            return msg.c_str();
        }
    };

    using uint_t = std::uint64_t;
    using str_t = std::string;
    using sstream_t = std::stringstream;
    using datetime = std::chrono::system_clock;
    using timestamp_t = std::chrono::system_clock::time_point;
    
    inline str_t
    format_timestamp(timestamp_t t) {
        return date::format("%F %T", t);
    }
    
} // namespace common
} // namespace aat