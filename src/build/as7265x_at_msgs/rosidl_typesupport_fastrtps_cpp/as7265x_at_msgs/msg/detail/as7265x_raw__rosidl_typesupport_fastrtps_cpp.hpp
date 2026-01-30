// generated from rosidl_typesupport_fastrtps_cpp/resource/idl__rosidl_typesupport_fastrtps_cpp.hpp.em
// with input from as7265x_at_msgs:msg/AS7265xRaw.idl
// generated code does not contain a copyright notice

#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__ROSIDL_TYPESUPPORT_FASTRTPS_CPP_HPP_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__ROSIDL_TYPESUPPORT_FASTRTPS_CPP_HPP_

#include <cstddef>
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_interface/macros.h"
#include "as7265x_at_msgs/msg/rosidl_typesupport_fastrtps_cpp__visibility_control.h"
#include "as7265x_at_msgs/msg/detail/as7265x_raw__struct.hpp"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

#include "fastcdr/Cdr.h"

namespace as7265x_at_msgs
{

namespace msg
{

namespace typesupport_fastrtps_cpp
{

bool
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
cdr_serialize(
  const as7265x_at_msgs::msg::AS7265xRaw & ros_message,
  eprosima::fastcdr::Cdr & cdr);

bool
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  as7265x_at_msgs::msg::AS7265xRaw & ros_message);

size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
get_serialized_size(
  const as7265x_at_msgs::msg::AS7265xRaw & ros_message,
  size_t current_alignment);

size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
max_serialized_size_AS7265xRaw(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

bool
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
cdr_serialize_key(
  const as7265x_at_msgs::msg::AS7265xRaw & ros_message,
  eprosima::fastcdr::Cdr &);

size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
get_serialized_size_key(
  const as7265x_at_msgs::msg::AS7265xRaw & ros_message,
  size_t current_alignment);

size_t
ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
max_serialized_size_key_AS7265xRaw(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

}  // namespace typesupport_fastrtps_cpp

}  // namespace msg

}  // namespace as7265x_at_msgs

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_FASTRTPS_CPP_PUBLIC_as7265x_at_msgs
const rosidl_message_type_support_t *
  ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_cpp, as7265x_at_msgs, msg, AS7265xRaw)();

#ifdef __cplusplus
}
#endif

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__ROSIDL_TYPESUPPORT_FASTRTPS_CPP_HPP_
