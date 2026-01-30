// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from as7265x_at_msgs:msg/AS7265xCal.idl
// generated code does not contain a copyright notice
#include "as7265x_at_msgs/msg/detail/as7265x_cal__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/detail/header__functions.h"

bool
as7265x_at_msgs__msg__AS7265xCal__init(as7265x_at_msgs__msg__AS7265xCal * msg)
{
  if (!msg) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__init(&msg->header)) {
    as7265x_at_msgs__msg__AS7265xCal__fini(msg);
    return false;
  }
  // values
  return true;
}

void
as7265x_at_msgs__msg__AS7265xCal__fini(as7265x_at_msgs__msg__AS7265xCal * msg)
{
  if (!msg) {
    return;
  }
  // header
  std_msgs__msg__Header__fini(&msg->header);
  // values
}

bool
as7265x_at_msgs__msg__AS7265xCal__are_equal(const as7265x_at_msgs__msg__AS7265xCal * lhs, const as7265x_at_msgs__msg__AS7265xCal * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__are_equal(
      &(lhs->header), &(rhs->header)))
  {
    return false;
  }
  // values
  for (size_t i = 0; i < 18; ++i) {
    if (lhs->values[i] != rhs->values[i]) {
      return false;
    }
  }
  return true;
}

bool
as7265x_at_msgs__msg__AS7265xCal__copy(
  const as7265x_at_msgs__msg__AS7265xCal * input,
  as7265x_at_msgs__msg__AS7265xCal * output)
{
  if (!input || !output) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__copy(
      &(input->header), &(output->header)))
  {
    return false;
  }
  // values
  for (size_t i = 0; i < 18; ++i) {
    output->values[i] = input->values[i];
  }
  return true;
}

as7265x_at_msgs__msg__AS7265xCal *
as7265x_at_msgs__msg__AS7265xCal__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  as7265x_at_msgs__msg__AS7265xCal * msg = (as7265x_at_msgs__msg__AS7265xCal *)allocator.allocate(sizeof(as7265x_at_msgs__msg__AS7265xCal), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(as7265x_at_msgs__msg__AS7265xCal));
  bool success = as7265x_at_msgs__msg__AS7265xCal__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
as7265x_at_msgs__msg__AS7265xCal__destroy(as7265x_at_msgs__msg__AS7265xCal * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    as7265x_at_msgs__msg__AS7265xCal__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
as7265x_at_msgs__msg__AS7265xCal__Sequence__init(as7265x_at_msgs__msg__AS7265xCal__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  as7265x_at_msgs__msg__AS7265xCal * data = NULL;

  if (size) {
    data = (as7265x_at_msgs__msg__AS7265xCal *)allocator.zero_allocate(size, sizeof(as7265x_at_msgs__msg__AS7265xCal), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = as7265x_at_msgs__msg__AS7265xCal__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        as7265x_at_msgs__msg__AS7265xCal__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
as7265x_at_msgs__msg__AS7265xCal__Sequence__fini(as7265x_at_msgs__msg__AS7265xCal__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      as7265x_at_msgs__msg__AS7265xCal__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

as7265x_at_msgs__msg__AS7265xCal__Sequence *
as7265x_at_msgs__msg__AS7265xCal__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  as7265x_at_msgs__msg__AS7265xCal__Sequence * array = (as7265x_at_msgs__msg__AS7265xCal__Sequence *)allocator.allocate(sizeof(as7265x_at_msgs__msg__AS7265xCal__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = as7265x_at_msgs__msg__AS7265xCal__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
as7265x_at_msgs__msg__AS7265xCal__Sequence__destroy(as7265x_at_msgs__msg__AS7265xCal__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    as7265x_at_msgs__msg__AS7265xCal__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
as7265x_at_msgs__msg__AS7265xCal__Sequence__are_equal(const as7265x_at_msgs__msg__AS7265xCal__Sequence * lhs, const as7265x_at_msgs__msg__AS7265xCal__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!as7265x_at_msgs__msg__AS7265xCal__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
as7265x_at_msgs__msg__AS7265xCal__Sequence__copy(
  const as7265x_at_msgs__msg__AS7265xCal__Sequence * input,
  as7265x_at_msgs__msg__AS7265xCal__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(as7265x_at_msgs__msg__AS7265xCal);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    as7265x_at_msgs__msg__AS7265xCal * data =
      (as7265x_at_msgs__msg__AS7265xCal *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!as7265x_at_msgs__msg__AS7265xCal__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          as7265x_at_msgs__msg__AS7265xCal__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!as7265x_at_msgs__msg__AS7265xCal__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
