# AMOS — Autonomous Mission Operating System
# Docker deployment for field operations
FROM ros:humble-ros-base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-colcon-common-extensions \
    ros-humble-mavros ros-humble-mavros-extras \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install flask pyyaml

# GeographicLib datasets (required by MAVROS)
RUN wget https://raw.githubusercontent.com/mavlink/mavros/ros2/mavros/scripts/install_geographiclib_datasets.sh \
    && bash install_geographiclib_datasets.sh || true && rm -f install_geographiclib_datasets.sh

# Copy workspace
WORKDIR /amos_ws
COPY src/ src/

# Build
RUN . /opt/ros/humble/setup.sh && colcon build

# Expose ports
EXPOSE 5000 6969/udp 14540/udp

# Entry
COPY launch_mos.sh /amos_ws/
RUN chmod +x /amos_ws/launch_mos.sh
COPY docker_entrypoint.sh /
RUN chmod +x /docker_entrypoint.sh
ENTRYPOINT ["/docker_entrypoint.sh"]
