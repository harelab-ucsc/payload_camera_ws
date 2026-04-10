/**
 * fast_stamp_split_node.cpp
 *
 * C++ port of stamp_and_split_cam1/pps_stamp_and_split.py
 *
 * Subscribes to:
 *   /pps/time                    (builtin_interfaces/msg/Time)
 *   /cam0/camera_node/image_raw  (sensor_msgs/msg/Image)
 *
 * Publishes 4 image slices:
 *   img0 .. img3                 (sensor_msgs/msg/Image)
 */

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <builtin_interfaces/msg/time.hpp>

#include <cv_bridge/cv_bridge.hpp>
#include <sensor_msgs/image_encodings.hpp>
#include <opencv2/opencv.hpp>

#include <mutex>
#include <optional>
#include <string>

using std::placeholders::_1;

class PpsStampAndSplitCpp : public rclcpp::Node
{
public:
  PpsStampAndSplitCpp()
  : rclcpp::Node("pps_stamp_and_split"),
    full_width_(5120),
    full_height_(800),
    num_slices_(4),
    slice_w_(0),
    require_pps_(true),
    have_pps_(false),
    warned_no_pps_(false)
  {
    // Parameters — mirrors Python node
    this->declare_parameter<std::string>("pps_topic", "/pps/time");
    this->declare_parameter<std::string>("in_topic", "/cam0/camera_node/image_raw");
    this->declare_parameter<std::string>("out_0", "img0");
    this->declare_parameter<std::string>("out_1", "img1");
    this->declare_parameter<std::string>("out_2", "img2");
    this->declare_parameter<std::string>("out_3", "img3");
    this->declare_parameter<bool>("require_pps", true);
    this->declare_parameter<int>("full_width", 5120);
    this->declare_parameter<int>("full_height", 800);
    this->declare_parameter<int>("num_slices", 4);
    this->declare_parameter<int>("pps_depth", 10);

    const std::string pps_topic   = this->get_parameter("pps_topic").as_string();
    const std::string in_topic    = this->get_parameter("in_topic").as_string();
    const std::string out_0_topic = this->get_parameter("out_0").as_string();
    const std::string out_1_topic = this->get_parameter("out_1").as_string();
    const std::string out_2_topic = this->get_parameter("out_2").as_string();
    const std::string out_3_topic = this->get_parameter("out_3").as_string();
    require_pps_  = this->get_parameter("require_pps").as_bool();
    full_width_   = this->get_parameter("full_width").as_int();
    full_height_  = this->get_parameter("full_height").as_int();
    num_slices_   = this->get_parameter("num_slices").as_int();
    const int pps_depth = this->get_parameter("pps_depth").as_int();

    slice_w_ = full_width_ / num_slices_;

    // QoS
    // Subscription to raw images: BEST_EFFORT to match camera_ros publisher
    rclcpp::SensorDataQoS img_sub_qos;
    // Slice publishers: RELIABLE so rosbag2 always captures all 4 slices from
    // each frame together.  Backpressure is negligible at 3 Hz.
    rclcpp::QoS slice_pub_qos(10);
    slice_pub_qos.reliability(RMW_QOS_POLICY_RELIABILITY_RELIABLE);
    slice_pub_qos.history(RMW_QOS_POLICY_HISTORY_KEEP_LAST);

    rclcpp::QoS pps_qos(static_cast<size_t>(pps_depth));
    pps_qos.reliability(RMW_QOS_POLICY_RELIABILITY_RELIABLE);
    pps_qos.history(RMW_QOS_POLICY_HISTORY_KEEP_LAST);

    // Subscriptions
    pps_sub_ = this->create_subscription<builtin_interfaces::msg::Time>(
      pps_topic, pps_qos,
      std::bind(&PpsStampAndSplitCpp::ppsCallback, this, _1));

    img_sub_ = this->create_subscription<sensor_msgs::msg::Image>(
      in_topic, img_sub_qos,
      std::bind(&PpsStampAndSplitCpp::imageCallback, this, _1));

    // Publishers
    pub0_ = this->create_publisher<sensor_msgs::msg::Image>(out_0_topic, slice_pub_qos);
    pub1_ = this->create_publisher<sensor_msgs::msg::Image>(out_1_topic, slice_pub_qos);
    pub2_ = this->create_publisher<sensor_msgs::msg::Image>(out_2_topic, slice_pub_qos);
    pub3_ = this->create_publisher<sensor_msgs::msg::Image>(out_3_topic, slice_pub_qos);

    RCLCPP_INFO(
      this->get_logger(),
      "PpsStampAndSplitCpp running:\n"
      "  pps_topic:   %s\n"
      "  in_topic:    %s\n"
      "  expect:      %dx%d -> %d slices of %dx%d\n"
      "  outs:        %s, %s, %s, %s\n"
      "  require_pps: %s",
      pps_topic.c_str(), in_topic.c_str(),
      full_width_, full_height_, num_slices_, slice_w_, full_height_,
      out_0_topic.c_str(), out_1_topic.c_str(),
      out_2_topic.c_str(), out_3_topic.c_str(),
      require_pps_ ? "true" : "false");
  }

private:
  void ppsCallback(const builtin_interfaces::msg::Time::SharedPtr msg)
  {
    std::lock_guard<std::mutex> lock(pps_mutex_);
    latest_pps_stamp_ = *msg;
    have_pps_ = true;
  }

  // Returns the stamp to use, or nullopt if frames should be dropped.
  // Reads have_pps_ exactly once inside the lock — no TOCTOU race.
  std::optional<builtin_interfaces::msg::Time> getStamp()
  {
    std::lock_guard<std::mutex> lock(pps_mutex_);
    if (!have_pps_) {
      if (require_pps_) {
        return std::nullopt;
      }
      return static_cast<builtin_interfaces::msg::Time>(this->now());
    }
    return latest_pps_stamp_;
  }

  void imageCallback(const sensor_msgs::msg::Image::SharedPtr msg)
  {
    auto maybe_stamp = getStamp();
    if (!maybe_stamp.has_value()) {
      if (!warned_no_pps_) {
        RCLCPP_WARN(this->get_logger(),
          "No PPS timestamp yet on %s; dropping frames until PPS arrives.",
          this->get_parameter("pps_topic").as_string().c_str());
        warned_no_pps_ = true;
      }
      return;
    }
    const builtin_interfaces::msg::Time stamp = maybe_stamp.value();

    // Geometry check
    const int w = static_cast<int>(msg->width);
    const int h = static_cast<int>(msg->height);
    if (w != full_width_ || h != full_height_) {
      RCLCPP_WARN(this->get_logger(),
        "Unexpected image size %dx%d (expected %dx%d). Splitting evenly anyway.",
        w, h, full_width_, full_height_);
    }

    // Decode — toCvShare shares memory when encoding is unchanged
    cv_bridge::CvImageConstPtr cv_ptr;
    try {
      cv_ptr = cv_bridge::toCvShare(msg, std::string());
    } catch (const cv_bridge::Exception & e) {
      RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
      return;
    }

    const cv::Mat & big = cv_ptr->image;
    const int slice_w = big.cols / num_slices_;

    if (slice_w == 0) {
      RCLCPP_ERROR(this->get_logger(),
        "slice_w == 0 (cols=%d, num_slices=%d)", big.cols, num_slices_);
      return;
    }

    // Slice into ROIs (zero-copy views)
    cv::Mat s0 = big(cv::Rect(0 * slice_w, 0, slice_w, big.rows));
    cv::Mat s1 = big(cv::Rect(1 * slice_w, 0, slice_w, big.rows));
    cv::Mat s2 = big(cv::Rect(2 * slice_w, 0, slice_w, big.rows));
    cv::Mat s3 = big(cv::Rect(3 * slice_w, 0, slice_w, big.rows));

    // Build output messages
    auto toMsg = [&](const cv::Mat & slice) {
      cv_bridge::CvImage cv_img(msg->header, msg->encoding, slice);
      auto out = cv_img.toImageMsg();
      out->header.stamp = stamp;
      return out;
    };

    pub0_->publish(*toMsg(s0));
    pub1_->publish(*toMsg(s1));
    pub2_->publish(*toMsg(s2));
    pub3_->publish(*toMsg(s3));
  }

  // Config
  int  full_width_;
  int  full_height_;
  int  num_slices_;
  int  slice_w_;
  bool require_pps_;

  // PPS state
  bool have_pps_;
  bool warned_no_pps_;
  builtin_interfaces::msg::Time latest_pps_stamp_;
  std::mutex pps_mutex_;

  // ROS interfaces
  rclcpp::Subscription<builtin_interfaces::msg::Time>::SharedPtr pps_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr       img_sub_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr          pub0_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr          pub1_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr          pub2_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr          pub3_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<PpsStampAndSplitCpp>());
  rclcpp::shutdown();
  return 0;
}
