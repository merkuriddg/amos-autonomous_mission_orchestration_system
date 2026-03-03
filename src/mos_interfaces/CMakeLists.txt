cmake_minimum_required(VERSION 3.8)
project(mos_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/AssetState.msg"
  "msg/MissionIntent.msg"
  "msg/TaskOrder.msg"
  "msg/ThreatContact.msg"
  "msg/ThreatAssessment.msg"
  "srv/AllocateTask.srv"
  DEPENDENCIES builtin_interfaces
)

ament_package()
