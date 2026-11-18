FROM ros:humble
SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-geographic-msgs ros-humble-rosidl-default-generators \
    python3-colcon-common-extensions python3-pip && rm -rf /var/lib/apt/lists/*
COPY interfaces /build/src
RUN source /opt/ros/humble/setup.bash && cd /build && colcon build
