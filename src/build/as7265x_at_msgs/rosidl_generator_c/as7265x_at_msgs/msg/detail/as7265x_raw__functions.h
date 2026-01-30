// generated from rosidl_generator_c/resource/idl__functions.h.em
// with input from as7265x_at_msgs:msg/AS7265xRaw.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "as7265x_at_msgs/msg/as7265x_raw.h"


#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__FUNCTIONS_H_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__FUNCTIONS_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stdlib.h>

#include "rosidl_runtime_c/action_type_support_struct.h"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_runtime_c/service_type_support_struct.h"
#include "rosidl_runtime_c/type_description/type_description__struct.h"
#include "rosidl_runtime_c/type_description/type_source__struct.h"
#include "rosidl_runtime_c/type_hash.h"
#include "rosidl_runtime_c/visibility_control.h"
#include "as7265x_at_msgs/msg/rosidl_generator_c__visibility_control.h"

#include "as7265x_at_msgs/msg/detail/as7265x_raw__struct.h"

/// Initialize msg/AS7265xRaw message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * as7265x_at_msgs__msg__AS7265xRaw
 * )) before or use
 * as7265x_at_msgs__msg__AS7265xRaw__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
bool
as7265x_at_msgs__msg__AS7265xRaw__init(as7265x_at_msgs__msg__AS7265xRaw * msg);

/// Finalize msg/AS7265xRaw message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
void
as7265x_at_msgs__msg__AS7265xRaw__fini(as7265x_at_msgs__msg__AS7265xRaw * msg);

/// Create msg/AS7265xRaw message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * as7265x_at_msgs__msg__AS7265xRaw__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
as7265x_at_msgs__msg__AS7265xRaw *
as7265x_at_msgs__msg__AS7265xRaw__create(void);

/// Destroy msg/AS7265xRaw message.
/**
 * It calls
 * as7265x_at_msgs__msg__AS7265xRaw__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
void
as7265x_at_msgs__msg__AS7265xRaw__destroy(as7265x_at_msgs__msg__AS7265xRaw * msg);

/// Check for msg/AS7265xRaw message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
bool
as7265x_at_msgs__msg__AS7265xRaw__are_equal(const as7265x_at_msgs__msg__AS7265xRaw * lhs, const as7265x_at_msgs__msg__AS7265xRaw * rhs);

/// Copy a msg/AS7265xRaw message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
bool
as7265x_at_msgs__msg__AS7265xRaw__copy(
  const as7265x_at_msgs__msg__AS7265xRaw * input,
  as7265x_at_msgs__msg__AS7265xRaw * output);

/// Retrieve pointer to the hash of the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
const rosidl_type_hash_t *
as7265x_at_msgs__msg__AS7265xRaw__get_type_hash(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
const rosidl_runtime_c__type_description__TypeDescription *
as7265x_at_msgs__msg__AS7265xRaw__get_type_description(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the single raw source text that defined this type.
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
const rosidl_runtime_c__type_description__TypeSource *
as7265x_at_msgs__msg__AS7265xRaw__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the recursive raw sources that defined the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
const rosidl_runtime_c__type_description__TypeSource__Sequence *
as7265x_at_msgs__msg__AS7265xRaw__get_type_description_sources(
  const rosidl_message_type_support_t * type_support);

/// Initialize array of msg/AS7265xRaw messages.
/**
 * It allocates the memory for the number of elements and calls
 * as7265x_at_msgs__msg__AS7265xRaw__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
bool
as7265x_at_msgs__msg__AS7265xRaw__Sequence__init(as7265x_at_msgs__msg__AS7265xRaw__Sequence * array, size_t size);

/// Finalize array of msg/AS7265xRaw messages.
/**
 * It calls
 * as7265x_at_msgs__msg__AS7265xRaw__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
void
as7265x_at_msgs__msg__AS7265xRaw__Sequence__fini(as7265x_at_msgs__msg__AS7265xRaw__Sequence * array);

/// Create array of msg/AS7265xRaw messages.
/**
 * It allocates the memory for the array and calls
 * as7265x_at_msgs__msg__AS7265xRaw__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
as7265x_at_msgs__msg__AS7265xRaw__Sequence *
as7265x_at_msgs__msg__AS7265xRaw__Sequence__create(size_t size);

/// Destroy array of msg/AS7265xRaw messages.
/**
 * It calls
 * as7265x_at_msgs__msg__AS7265xRaw__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
void
as7265x_at_msgs__msg__AS7265xRaw__Sequence__destroy(as7265x_at_msgs__msg__AS7265xRaw__Sequence * array);

/// Check for msg/AS7265xRaw message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
bool
as7265x_at_msgs__msg__AS7265xRaw__Sequence__are_equal(const as7265x_at_msgs__msg__AS7265xRaw__Sequence * lhs, const as7265x_at_msgs__msg__AS7265xRaw__Sequence * rhs);

/// Copy an array of msg/AS7265xRaw messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_as7265x_at_msgs
bool
as7265x_at_msgs__msg__AS7265xRaw__Sequence__copy(
  const as7265x_at_msgs__msg__AS7265xRaw__Sequence * input,
  as7265x_at_msgs__msg__AS7265xRaw__Sequence * output);

#ifdef __cplusplus
}
#endif

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__FUNCTIONS_H_
