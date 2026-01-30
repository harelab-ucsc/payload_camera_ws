// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from as7265x_at_msgs:msg/AS7265xCal.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "as7265x_at_msgs/msg/as7265x_cal.hpp"


#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__TRAITS_HPP_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "as7265x_at_msgs/msg/detail/as7265x_cal__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__traits.hpp"

namespace as7265x_at_msgs
{

namespace msg
{

inline void to_flow_style_yaml(
  const AS7265xCal & msg,
  std::ostream & out)
{
  out << "{";
  // member: header
  {
    out << "header: ";
    to_flow_style_yaml(msg.header, out);
    out << ", ";
  }

  // member: values
  {
    if (msg.values.size() == 0) {
      out << "values: []";
    } else {
      out << "values: [";
      size_t pending_items = msg.values.size();
      for (auto item : msg.values) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const AS7265xCal & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: header
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "header:\n";
    to_block_style_yaml(msg.header, out, indentation + 2);
  }

  // member: values
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.values.size() == 0) {
      out << "values: []\n";
    } else {
      out << "values:\n";
      for (auto item : msg.values) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const AS7265xCal & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace msg

}  // namespace as7265x_at_msgs

namespace rosidl_generator_traits
{

[[deprecated("use as7265x_at_msgs::msg::to_block_style_yaml() instead")]]
inline void to_yaml(
  const as7265x_at_msgs::msg::AS7265xCal & msg,
  std::ostream & out, size_t indentation = 0)
{
  as7265x_at_msgs::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use as7265x_at_msgs::msg::to_yaml() instead")]]
inline std::string to_yaml(const as7265x_at_msgs::msg::AS7265xCal & msg)
{
  return as7265x_at_msgs::msg::to_yaml(msg);
}

template<>
inline const char * data_type<as7265x_at_msgs::msg::AS7265xCal>()
{
  return "as7265x_at_msgs::msg::AS7265xCal";
}

template<>
inline const char * name<as7265x_at_msgs::msg::AS7265xCal>()
{
  return "as7265x_at_msgs/msg/AS7265xCal";
}

template<>
struct has_fixed_size<as7265x_at_msgs::msg::AS7265xCal>
  : std::integral_constant<bool, has_fixed_size<std_msgs::msg::Header>::value> {};

template<>
struct has_bounded_size<as7265x_at_msgs::msg::AS7265xCal>
  : std::integral_constant<bool, has_bounded_size<std_msgs::msg::Header>::value> {};

template<>
struct is_message<as7265x_at_msgs::msg::AS7265xCal>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__TRAITS_HPP_
