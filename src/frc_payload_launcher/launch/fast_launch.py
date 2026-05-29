#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import RegisterEventHandler, TimerAction, DeclareLaunchArgument, Shutdown
from launch.substitutions import LaunchConfiguration
from launch.event_handlers import OnProcessStart, OnProcessExit


def generate_launch_description():
    # Declare arguments
    val = "/home/pi5-alpha/ros2/ros2_iron/src/inertial-sense-sdk/ros2/launch/example_params.yaml"

    force_cal_arg = DeclareLaunchArgument(
        "force_cal",
        default_value="false",
        description=(
            "Set to 'true' to skip the 6 m AGL altitude gate and run "
            "auto-calibration immediately on startup. Use only for ground "
            "testing — in normal flight this should be 'false'."
        ),
    )

    indoor_cal_arg = DeclareLaunchArgument(
        "indoor_cal",
        default_value="5000",
        description=(
            "Override auto_cal's max exposure in microseconds. Default 5000 µs "
            "is the flight-safe limit (< 1 px smear at 5 m/s). Set higher for "
            "indoor testing where more exposure is needed to see the QR tag. "
            "Example: indoor_cal:=33333 for ~30 fps max. NEVER use in flight."
        ),
    )

    yaml_param_file_arg = DeclareLaunchArgument(
        "yaml_param_file",
        default_value=val,
        description="Path to the YAML parameter file for the inertial_sense_ros2 node",
    )

    antenna_offset_gps1_arg = DeclareLaunchArgument(
        "antenna_offset_gps1",
        default_value="[-0.02, 0.48, -0.36]",  # Default value; update as needed
        description="Offset for GPS1 antenna",
    )

    mag_declination_arg = DeclareLaunchArgument(
        "mag_declination",
        default_value="0.222",  # Default value; update as needed
        description="Magnetic declination value",
    )

    # Get the argument values
    yaml_param_file = LaunchConfiguration("yaml_param_file")
    antenna_offset_gps1 = LaunchConfiguration("antenna_offset_gps1")
    mag_declination = LaunchConfiguration("mag_declination")
    force_cal = LaunchConfiguration("force_cal")
    indoor_cal = LaunchConfiguration("indoor_cal")

    # ------------------------------------------------------------------
    # PPS node — shared by both cameras
    # ------------------------------------------------------------------
    pps = Node(
        package="pps_time_pub",
        executable="pps_time_pub",
        name="pps_time_pub",
        output="screen",
        parameters=[{
            "pps_device": "/dev/pps0",
            "pps_topic": "/pps/time",
            "use_sudo": True,
        }],
    )

    # -------------------------------------------------------------------
    # Radar altimeter, spectrometer, and INS nodes
    # -------------------------------------------------------------------
    radalt = Node(
        package="ros2_radalt", executable="radalt", name="radalt", output="screen"
    )

    spectrometer = Node(
        package="as7265x_at",
        executable="as7265x_at_node",
        name="as7265x_at_node",
        output="screen",
    )

    # Inertial Sense node with parameters
    inertial_sense_node = Node(
        package="inertial_sense_ros2",
        executable="new_target",
        name="inertial_sense_node",
        output="screen",
        arguments=[yaml_param_file],
        parameters=[
            {"antenna_offset_gps1": antenna_offset_gps1},
            {"mag_declination": mag_declination},
        ],
    )

    # ------------------------------------------------------------------
    # cam0 — mono sensor (arducam-pivariety 4-000c)
    # ------------------------------------------------------------------
    cam0 = Node(
        package="camera_ros",
        executable="camera_node",
        name="camera_node",
        namespace="cam0",
        output="screen",
        parameters=[
            {"camera": 0},
            {"role": "video"},
            {"width": 5120},
            {"height": 800},
            {"frame_id": "cam0_optical_frame"},
            {"format": "R16"},
            # role="video" instead of "still": the still role configures the IPA
            # with ExposureTimeMode semantics that block all dynamic ExposureTime
            # updates (AeEnable=False internally activates ExposureTimeMode=Manual,
            # after which ExposureTime is rejected). The video role keeps the IPA
            # in streaming mode, which allows ExposureTime to be set directly.
            # Capture rate is the external PWM trigger regardless of role.
        ],
    )

    # ------------------------------------------------------------------
    # cam1 — color Bayer sensor (arducam-pivariety 6-000c)
    # ------------------------------------------------------------------
    # NOTE: FrameDurationLimits is intentionally omitted for cam1.
    # cam1 uses SBGGR16 (Bayer/ISP), where the "still" role implicitly
    # activates ExposureTimeMode=Manual. Pinning FrameDurationLimits
    # [min==max] also implicitly sets ExposureTime, triggering a libcamera
    # conflict that produces a spurious warning and unreliable AE state.
    # Actual capture rate is controlled by the external PWM trigger.
    cam1 = Node(
        package="camera_ros",
        executable="camera_node",
        name="camera_node",
        namespace="cam1",
        output="screen",
        parameters=[
            {"camera": 1},
            {"role": "still"},
            {"width": 5120},
            {"height": 800},
            {"frame_id": "cam1_optical_frame"},
            {"format": "SBGGR16"},
        ],
    )

    # ------------------------------------------------------------------
    # MicaCRPCal — panel scan node.
    # Waits for /cal/exposure_locked from auto_cal (published once cameras are
    # locked at flight exposure settings at 6 m AGL), then opens a 30 s window
    # to detect the CRP QR tag via cam0.  On confirmation it extracts per-band
    # panel DN at the locked exposure, applies the certified CRP albedo, and
    # publishes 4 reflectance correction factors on /panel_cal/irradiance
    # (latched).  Exits after publishing or timeout.
    # NOTE: place the panel flat on the ground below the hovering drone,
    # in direct sunlight with NO shadow on the reflective surface.
    # ------------------------------------------------------------------
    panel_scan = Node(
        package="mica_crp_cal",
        executable="panel_scan",
        name="panel_scan",
        output="screen",
        parameters=[{"force_cal": force_cal}],
    )

    # ------------------------------------------------------------------
    # AutoCalNode — exposure lock + irradiance reference at 6 m AGL.
    # Subscribes to radalt, cam0, cam1, and the spectrometer. Waits for the
    # drone to clear 6 m, binary-searches ExposureTime and AnalogueGain for
    # each camera (preferring low gain to minimise noise), locks both cameras,
    # then publishes the spectrometer snapshot on /panel_cal/spec_ref (latched)
    # for stream_processor's per-cycle irradiance ratio correction.
    # Starts at t=6 s so both cameras are live and publishing.
    # ------------------------------------------------------------------
    auto_cal = Node(
        package="mica_crp_cal",
        executable="auto_cal",
        name="auto_cal",
        output="screen",
        parameters=[{"force_cal": force_cal, "max_exposure_us": indoor_cal}],
    )

    # ------------------------------------------------------------------
    # stream_processor — PPS-synced save node (does split + spectral
    # correction + debayer in-process via the C++ extension; no
    # intermediate image topics on DDS)
    # ------------------------------------------------------------------
    sync_node = Node(
        package="stream_processor",
        executable="sync_node",
        name="sync_node",
        output="screen",
        parameters=[{
            "db_name": "flight_data",
            "img_format": ".tiff",
            "dir_name": "parsed_flight",
            "sensors_yaml": "sensor_params/birdsEyeSensorParams.yaml",
            "clicks_csv": "catch/data.csv",
            "framerate": 3.0,
            "gsd_m": 0.03,   # metres/pixel — update once optics are calibrated
        }],
    )

    # ------------------------------------------------------------------
    # Sequencing:
    #   t=0.0s   pps starts
    #   t=2.0s   cam0 starts
    #   t=4.0s   cam1 starts (staggered to avoid I2C init collision)
    #   t=6.0s   sync_node (stream_processor) starts
    # ------------------------------------------------------------------
    delayed_cam0 = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=2.0,
                    actions=[cam0],
                )
            ],
        )
    )

    delayed_cam1 = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=4.0,
                    actions=[cam1],
                )
            ],
        )
    )

    delayed_sync = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=6.0,
                    actions=[sync_node],
                )
            ],
        )
    )

    # panel_scan and auto_cal both start at t=6 s (both cameras live).
    # panel_scan self-gates on /cal/exposure_locked published by auto_cal,
    # so the actual QR scan window only opens after cameras are locked.
    delayed_panel_scan = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=6.0,
                    actions=[panel_scan],
                )
            ],
        )
    )

    # auto_cal starts at t=6 s and self-gates on radalt > 6 m before running
    # the exposure binary search.
    delayed_auto_cal = RegisterEventHandler(
        OnProcessStart(
            target_action=pps,
            on_start=[
                TimerAction(
                    period=6.0,
                    actions=[auto_cal],
                )
            ],
        )
    )

    return LaunchDescription(
        [
            force_cal_arg,
            indoor_cal_arg,
            yaml_param_file_arg,
            antenna_offset_gps1_arg,
            mag_declination_arg,
            pps,
            radalt,
            spectrometer,
            inertial_sense_node,
            delayed_cam0,
            delayed_cam1,
            delayed_panel_scan,
            delayed_auto_cal,
            delayed_sync,
        ]
    )
