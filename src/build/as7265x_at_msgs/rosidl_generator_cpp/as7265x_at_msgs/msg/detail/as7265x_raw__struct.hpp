// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from as7265x_at_msgs:msg/AS7265xRaw.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "as7265x_at_msgs/msg/as7265x_raw.hpp"


#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__STRUCT_HPP_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__as7265x_at_msgs__msg__AS7265xRaw __attribute__((deprecated))
#else
# define DEPRECATED__as7265x_at_msgs__msg__AS7265xRaw __declspec(deprecated)
#endif

namespace as7265x_at_msgs
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct AS7265xRaw_
{
  using Type = AS7265xRaw_<ContainerAllocator>;

  explicit AS7265xRaw_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      std::fill<typename std::array<int32_t, 18>::iterator, int32_t>(this->values.begin(), this->values.end(), 0l);
    }
  }

  explicit AS7265xRaw_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_alloc, _init),
    values(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      std::fill<typename std::array<int32_t, 18>::iterator, int32_t>(this->values.begin(), this->values.end(), 0l);
    }
  }

  // field types and members
  using _header_type =
    std_msgs::msg::Header_<ContainerAllocator>;
  _header_type header;
  using _values_type =
    std::array<int32_t, 18>;
  _values_type values;

  // setters for named parameter idiom
  Type & set__header(
    const std_msgs::msg::Header_<ContainerAllocator> & _arg)
  {
    this->header = _arg;
    return *this;
  }
  Type & set__values(
    const std::array<int32_t, 18> & _arg)
  {
    this->values = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator> *;
  using ConstRawPtr =
    const as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__as7265x_at_msgs__msg__AS7265xRaw
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__as7265x_at_msgs__msg__AS7265xRaw
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xRaw_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const AS7265xRaw_ & other) const
  {
    if (this->header != other.header) {
      return false;
    }
    if (this->values != other.values) {
      return false;
    }
    return true;
  }
  bool operator!=(const AS7265xRaw_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct AS7265xRaw_

// alias to use template instance with default allocator
using AS7265xRaw =
  as7265x_at_msgs::msg::AS7265xRaw_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace as7265x_at_msgs

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_RAW__STRUCT_HPP_
