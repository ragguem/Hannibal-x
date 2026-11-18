cmake_minimum_required(VERSION 3.8)
project(lotusim_old_msgs)
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(geographic_msgs REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/VesselPosition2.msg"
  "msg/VesselPositionArray2.msg"
  DEPENDENCIES std_msgs geometry_msgs geographic_msgs)
ament_package()
