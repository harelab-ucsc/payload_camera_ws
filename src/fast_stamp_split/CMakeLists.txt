cmake_minimum_required(VERSION 3.8)
project(fast_stamp_split)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)

# Executable
add_executable(fast_stamp_split_node
  src/fast_stamp_split_node.cpp
)

target_include_directories(fast_stamp_split_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${OpenCV_INCLUDE_DIRS}
)

ament_target_dependencies(fast_stamp_split_node
  rclcpp
  sensor_msgs
  builtin_interfaces
  cv_bridge
)

target_link_libraries(fast_stamp_split_node
  ${OpenCV_LIBS}
)

# Install
install(TARGETS fast_stamp_split_node
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
