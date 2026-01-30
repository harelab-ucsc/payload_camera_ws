// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from as7265x_at_msgs:msg/AS7265xRaw.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "as7265x_at_msgs/msg/as7265x_raw.h"


#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__STRUCT_H_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Constants defined in the message

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__struct.h"

/// Struct defined in msg/AS7265xRaw in the package as7265x_at_msgs.
typedef struct as7265x_at_msgs__msg__AS7265xRaw
{
  std_msgs__msg__Header header;
  /// raw spectrometer data
  int32_t values[18];
} as7265x_at_msgs__msg__AS7265xRaw;

// Struct for a sequence of as7265x_at_msgs__msg__AS7265xRaw.
typedef struct as7265x_at_msgs__msg__AS7265xRaw__Sequence
{
  as7265x_at_msgs__msg__AS7265xRaw * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} as7265x_at_msgs__msg__AS7265xRaw__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__STRUCT_H_
