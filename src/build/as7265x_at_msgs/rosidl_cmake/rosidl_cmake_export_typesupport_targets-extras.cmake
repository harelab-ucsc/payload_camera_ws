# generated from
# rosidl_cmake/cmake/template/rosidl_cmake_export_typesupport_targets.cmake.in

set(_exported_typesupport_targets
  "__rosidl_generator_c:as7265x_at_msgs__rosidl_generator_c;__rosidl_typesupport_introspection_c:as7265x_at_msgs__rosidl_typesupport_introspection_c;__rosidl_typesupport_fastrtps_c:as7265x_at_msgs__rosidl_typesupport_fastrtps_c;__rosidl_typesupport_c:as7265x_at_msgs__rosidl_typesupport_c;__rosidl_generator_cpp:as7265x_at_msgs__rosidl_generator_cpp;__rosidl_typesupport_introspection_cpp:as7265x_at_msgs__rosidl_typesupport_introspection_cpp;__rosidl_typesupport_fastrtps_cpp:as7265x_at_msgs__rosidl_typesupport_fastrtps_cpp;__rosidl_typesupport_cpp:as7265x_at_msgs__rosidl_typesupport_cpp;:as7265x_at_msgs__rosidl_generator_py")

# populate as7265x_at_msgs_TARGETS_<suffix>
if(NOT _exported_typesupport_targets STREQUAL "")
  # loop over typesupport targets
  foreach(_tuple ${_exported_typesupport_targets})
    string(REPLACE ":" ";" _tuple "${_tuple}")
    list(GET _tuple 0 _suffix)
    list(GET _tuple 1 _target)

    set(_target "as7265x_at_msgs::${_target}")
    if(NOT TARGET "${_target}")
      # the exported target must exist
      message(WARNING "Package 'as7265x_at_msgs' exports the typesupport target '${_target}' which doesn't exist")
    else()
      list(APPEND as7265x_at_msgs_TARGETS${_suffix} "${_target}")
    endif()
  endforeach()
endif()
