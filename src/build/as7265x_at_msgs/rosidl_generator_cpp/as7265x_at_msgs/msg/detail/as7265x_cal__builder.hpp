// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from as7265x_at_msgs:msg/AS7265xCal.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "as7265x_at_msgs/msg/as7265x_cal.hpp"


#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__BUILDER_HPP_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "as7265x_at_msgs/msg/detail/as7265x_cal__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace as7265x_at_msgs
{

namespace msg
{

namespace builder
{

class Init_AS7265xCal_values
{
public:
  explicit Init_AS7265xCal_values(::as7265x_at_msgs::msg::AS7265xCal & msg)
  : msg_(msg)
  {}
  ::as7265x_at_msgs::msg::AS7265xCal values(::as7265x_at_msgs::msg::AS7265xCal::_values_type arg)
  {
    msg_.values = std::move(arg);
    return std::move(msg_);
  }

private:
  ::as7265x_at_msgs::msg::AS7265xCal msg_;
};

class Init_AS7265xCal_header
{
public:
  Init_AS7265xCal_header()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_AS7265xCal_values header(::as7265x_at_msgs::msg::AS7265xCal::_header_type arg)
  {
    msg_.header = std::move(arg);
    return Init_AS7265xCal_values(msg_);
  }

private:
  ::as7265x_at_msgs::msg::AS7265xCal msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::as7265x_at_msgs::msg::AS7265xCal>()
{
  return as7265x_at_msgs::msg::builder::Init_AS7265xCal_header();
}

}  // namespace as7265x_at_msgs

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__BUILDER_HPP_
