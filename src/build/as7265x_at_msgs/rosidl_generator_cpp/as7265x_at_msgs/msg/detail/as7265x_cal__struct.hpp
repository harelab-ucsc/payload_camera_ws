// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from as7265x_at_msgs:msg/AS7265xCal.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "as7265x_at_msgs/msg/as7265x_cal.hpp"


#ifndef AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__STRUCT_HPP_
#define AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__STRUCT_HPP_

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
# define DEPRECATED__as7265x_at_msgs__msg__AS7265xCal __attribute__((deprecated))
#else
# define DEPRECATED__as7265x_at_msgs__msg__AS7265xCal __declspec(deprecated)
#endif

namespace as7265x_at_msgs
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct AS7265xCal_
{
  using Type = AS7265xCal_<ContainerAllocator>;

  explicit AS7265xCal_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      std::fill<typename std::array<float, 18>::iterator, float>(this->values.begin(), this->values.end(), 0.0f);
    }
  }

  explicit AS7265xCal_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_alloc, _init),
    values(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      std::fill<typename std::array<float, 18>::iterator, float>(this->values.begin(), this->values.end(), 0.0f);
    }
  }

  // field types and members
  using _header_type =
    std_msgs::msg::Header_<ContainerAllocator>;
  _header_type header;
  using _values_type =
    std::array<float, 18>;
  _values_type values;

  // setters for named parameter idiom
  Type & set__header(
    const std_msgs::msg::Header_<ContainerAllocator> & _arg)
  {
    this->header = _arg;
    return *this;
  }
  Type & set__values(
    const std::array<float, 18> & _arg)
  {
    this->values = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator> *;
  using ConstRawPtr =
    const as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__as7265x_at_msgs__msg__AS7265xCal
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__as7265x_at_msgs__msg__AS7265xCal
    std::shared_ptr<as7265x_at_msgs::msg::AS7265xCal_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const AS7265xCal_ & other) const
  {
    if (this->header != other.header) {
      return false;
    }
    if (this->values != other.values) {
      return false;
    }
    return true;
  }
  bool operator!=(const AS7265xCal_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct AS7265xCal_

// alias to use template instance with default allocator
using AS7265xCal =
  as7265x_at_msgs::msg::AS7265xCal_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace as7265x_at_msgs

#endif  // AS7265X_AT_MSGS__MSG__DETAIL__AS7265X_CAL__STRUCT_HPP_
