// generated from rosidl_typesupport_introspection_cpp/resource/idl__type_support.cpp.em
// with input from as7265x_at_msgs:msg/AS7265xRaw.idl
// generated code does not contain a copyright notice

#include "array"
#include "cstddef"
#include "string"
#include "vector"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_cpp/message_type_support.hpp"
#include "rosidl_typesupport_interface/macros.h"
#include "as7265x_at_msgs/msg/detail/as7265x_raw__functions.h"
#include "as7265x_at_msgs/msg/detail/as7265x_raw__struct.hpp"
#include "rosidl_typesupport_introspection_cpp/field_types.hpp"
#include "rosidl_typesupport_introspection_cpp/identifier.hpp"
#include "rosidl_typesupport_introspection_cpp/message_introspection.hpp"
#include "rosidl_typesupport_introspection_cpp/message_type_support_decl.hpp"
#include "rosidl_typesupport_introspection_cpp/visibility_control.h"

namespace as7265x_at_msgs
{

namespace msg
{

namespace rosidl_typesupport_introspection_cpp
{

void AS7265xRaw_init_function(
  void * message_memory, rosidl_runtime_cpp::MessageInitialization _init)
{
  new (message_memory) as7265x_at_msgs::msg::AS7265xRaw(_init);
}

void AS7265xRaw_fini_function(void * message_memory)
{
  auto typed_message = static_cast<as7265x_at_msgs::msg::AS7265xRaw *>(message_memory);
  typed_message->~AS7265xRaw();
}

size_t size_function__AS7265xRaw__values(const void * untyped_member)
{
  (void)untyped_member;
  return 18;
}

const void * get_const_function__AS7265xRaw__values(const void * untyped_member, size_t index)
{
  const auto & member =
    *reinterpret_cast<const std::array<int32_t, 18> *>(untyped_member);
  return &member[index];
}

void * get_function__AS7265xRaw__values(void * untyped_member, size_t index)
{
  auto & member =
    *reinterpret_cast<std::array<int32_t, 18> *>(untyped_member);
  return &member[index];
}

void fetch_function__AS7265xRaw__values(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const auto & item = *reinterpret_cast<const int32_t *>(
    get_const_function__AS7265xRaw__values(untyped_member, index));
  auto & value = *reinterpret_cast<int32_t *>(untyped_value);
  value = item;
}

void assign_function__AS7265xRaw__values(
  void * untyped_member, size_t index, const void * untyped_value)
{
  auto & item = *reinterpret_cast<int32_t *>(
    get_function__AS7265xRaw__values(untyped_member, index));
  const auto & value = *reinterpret_cast<const int32_t *>(untyped_value);
  item = value;
}

static const ::rosidl_typesupport_introspection_cpp::MessageMember AS7265xRaw_message_member_array[2] = {
  {
    "header",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    ::rosidl_typesupport_introspection_cpp::get_message_type_support_handle<std_msgs::msg::Header>(),  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(as7265x_at_msgs::msg::AS7265xRaw, header),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "values",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_INT32,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    true,  // is array
    18,  // array size
    false,  // is upper bound
    offsetof(as7265x_at_msgs::msg::AS7265xRaw, values),  // bytes offset in struct
    nullptr,  // default value
    size_function__AS7265xRaw__values,  // size() function pointer
    get_const_function__AS7265xRaw__values,  // get_const(index) function pointer
    get_function__AS7265xRaw__values,  // get(index) function pointer
    fetch_function__AS7265xRaw__values,  // fetch(index, &value) function pointer
    assign_function__AS7265xRaw__values,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  }
};

static const ::rosidl_typesupport_introspection_cpp::MessageMembers AS7265xRaw_message_members = {
  "as7265x_at_msgs::msg",  // message namespace
  "AS7265xRaw",  // message name
  2,  // number of fields
  sizeof(as7265x_at_msgs::msg::AS7265xRaw),
  false,  // has_any_key_member_
  AS7265xRaw_message_member_array,  // message members
  AS7265xRaw_init_function,  // function to initialize message memory (memory has to be allocated)
  AS7265xRaw_fini_function  // function to terminate message instance (will not free memory)
};

static const rosidl_message_type_support_t AS7265xRaw_message_type_support_handle = {
  ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  &AS7265xRaw_message_members,
  get_message_typesupport_handle_function,
  &as7265x_at_msgs__msg__AS7265xRaw__get_type_hash,
  &as7265x_at_msgs__msg__AS7265xRaw__get_type_description,
  &as7265x_at_msgs__msg__AS7265xRaw__get_type_description_sources,
};

}  // namespace rosidl_typesupport_introspection_cpp

}  // namespace msg

}  // namespace as7265x_at_msgs


namespace rosidl_typesupport_introspection_cpp
{

template<>
ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
get_message_type_support_handle<as7265x_at_msgs::msg::AS7265xRaw>()
{
  return &::as7265x_at_msgs::msg::rosidl_typesupport_introspection_cpp::AS7265xRaw_message_type_support_handle;
}

}  // namespace rosidl_typesupport_introspection_cpp

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, as7265x_at_msgs, msg, AS7265xRaw)() {
  return &::as7265x_at_msgs::msg::rosidl_typesupport_introspection_cpp::AS7265xRaw_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif
