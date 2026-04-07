# ROS2 Iron base — multi-arch (amd64 + arm64v8 native for Raspberry Pi)
# Ubuntu 22.04 Jammy, includes: colcon, rosdep, vcstool, build-essential, git
FROM ros:iron-ros-base

# ─── System dependencies ────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    # libcamera: backend driver required by camera_ros (Raspberry Pi Camera)
    libcamera-dev \
    # OpenCV: required by fast_stamp_split (C++) and cv_bridge (vendored)
    libopencv-dev \
    python3-opencv \
    # Boost Python: required by vendored cv_bridge
    libboost-dev \
    libboost-python-dev \
    # Python utilities
    python3-numpy \
    python3-pip \
    # Serial comms for AS7265x spectral sensor
    python3-serial \
    # ROS packages not reliably resolved by rosdep on iron snapshots
    ros-iron-camera-info-manager \
    ros-iron-image-transport \
    ros-iron-image-view \
    && rm -rf /var/lib/apt/lists/*

# ─── Python dependencies ─────────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt Deprecated

# ─── Copy workspace from local directory ─────────────────────────────────────
WORKDIR /payload_camera_ws
COPY . .

# ─── rosdep: install all ROS package dependencies from package.xml files ─────
RUN rosdep update && \
    . /opt/ros/iron/setup.sh && \
    rosdep install \
        --from-paths src \
        --ignore-src \
        --rosdistro iron \
        --skip-keys "libcamera OpenCV camera_info_manager image_transport image_view python3-deprecated ament_cmake_pyflakes ament_cmake_mypy ament_cmake_pep257 ament_cmake_flake8 ament_cmake_lint_cmake ament_cmake_cppcheck ament_cmake_clang_format ament_cmake_xmllint clang-format" \
        -y

# ─── Build the workspace ──────────────────────────────────────────────────────
# camera_ros and camera_ros_bringup require libcamera>=0.1 (Raspberry Pi only).
# Ubuntu 22.04 ships libcamera 0~git20200629 which is too old for x86 builds.
# These packages are skipped here; on real Pi hardware colcon build runs without
# --packages-skip and they will build against the Pi's native libcamera.
RUN . /opt/ros/iron/setup.sh && \
    colcon build \
        --symlink-install \
        --packages-skip camera_ros camera_ros_bringup \
        --cmake-args -DCMAKE_BUILD_TYPE=Release

# ─── Integration test (optional: pass --build-arg RUN_TESTS=true to enable) ───
RUN pip3 install --no-cache-dir pytest
ARG RUN_TESTS=false
RUN if [ "$RUN_TESTS" = "true" ]; then \
        bash docker/run_tests.sh; \
    fi

# ─── Entrypoint ───────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
