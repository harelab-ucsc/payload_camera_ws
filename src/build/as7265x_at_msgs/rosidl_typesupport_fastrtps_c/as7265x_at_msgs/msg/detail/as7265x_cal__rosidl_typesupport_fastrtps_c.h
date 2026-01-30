// generated from rosidl_typesupport_fastrtps_c/resource/idl__rosidl_typesupport_fastrtps_c.h.em
// with input from as7265x_at_msgs:msg/AS7265xCal.idl
// generated code does not contain a copyright notice
#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_


#include <stddef.h>
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_interface/macros.h"
#include "as7265x_at_msgs/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "as7265x_at_msgs/msg/detail/as7265x_cal__struct.h"
#include "fastcdr/Cdr.h"

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
bool cdr_serialize_as7265x_at_msgs__msg__AS7265xCal(
  const as7265x_at_msgs__msg__AS7265xCal * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
bool cdr_deserialize_as7265x_at_msgs__msg__AS7265xCal(
  eprosima::fastcdr::Cdr &,
  as7265x_at_msgs__msg__AS7265xCal * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
size_t get_serialized_size_as7265x_at_msgs__msg__AS7265xCal(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
size_t max_serialized_size_as7265x_at_msgs__msg__AS7265xCal(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
bool cdr_serialize_key_as7265x_at_msgs__msg__AS7265xCal(
  const as7265x_at_msgs__msg__AS7265xCal * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
size_t get_serialized_size_key_as7265x_at_msgs__msg__AS7265xCal(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
size_t max_serialized_size_key_as7265x_at_msgs__msg__AS7265xCal(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_as7265x_at_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, as7265x_at_msgs, msg, AS7265xCal)();

#ifdef __cplusplus
}
#endif

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
