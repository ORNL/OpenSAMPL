"""
TimeProvider 4100 modem data collection module.

This module provides configuration classes and utilities for collecting performance
monitoring data from Microchip TimeProvider 4100 devices. It defines metrics,
channel configurations, and monitoring parameters for various timing interfaces.
"""

from dataclasses import dataclass
from typing import ClassVar, Optional


@dataclass
class MetricInfo:
    """
    Information about a performance monitoring metric.

    Attributes:
        short_name: Short identifier for the metric.
        full_name: Human-readable description of the metric.
        metric_id: Numeric ID used by the device API.

    """

    short_name: str
    full_name: str
    metric_id: int


class MONITOR_METRIC:  # noqa: N801
    """
    Available monitoring metrics for TimeProvider 4100 devices.

    This class defines all available performance monitoring metrics that can be
    collected from TP4100 devices, organized by category (time error, PTP, time interval).
    """

    TE = MetricInfo(short_name="te", full_name="time-error (ns)", metric_id=0)
    CTE = MetricInfo(short_name="cte", full_name="constant time-error (ns)", metric_id=1)
    MAX_TE = MetricInfo(short_name="max-te", full_name="max time-error (ns)", metric_id=2)

    FLOOR_FWD = MetricInfo(short_name="floor_fwd", full_name="Floor Forward (ns)", metric_id=7)
    FLOOR_REV = MetricInfo(short_name="floor_rev", full_name="Floor Reverse (ns)", metric_id=8)

    FPP1_FWD = MetricInfo(short_name="fpp1_fwd", full_name="FPP1 Forward (%)", metric_id=3)
    FPP1_REV = MetricInfo(short_name="fpp1_rev", full_name="FPP1 Reverse (%)", metric_id=4)

    FPP2_FWD = MetricInfo(short_name="fpp2_fwd", full_name="FPP2 Forward (%)", metric_id=5)
    FPP2_REV = MetricInfo(short_name="fpp2_rev", full_name="FPP2 Reverse (%)", metric_id=6)

    MTIE = MetricInfo(short_name="mtie", full_name="MTIE (ns)", metric_id=9)
    TDEV = MetricInfo(short_name="tdev", full_name="TDEV", metric_id=11)
    TDEVP = MetricInfo(short_name="tdev_p", full_name="TDEV w/ Population", metric_id=10)
    TIE = MetricInfo(short_name="tie", full_name="TIE", metric_id=12)

    TIME_ERROR: ClassVar = [TE, CTE, MAX_TE]
    PTP: ClassVar = [TE, CTE, MAX_TE, FLOOR_FWD, FLOOR_REV, FPP1_FWD, FPP1_REV, FPP2_REV, FPP2_FWD]
    TIME_INTERVAL: ClassVar = [MTIE, TDEV, TDEVP, TIE]


@dataclass
class MonitoringConfig:
    """
    Configuration for monitoring a specific channel type.

    Attributes:
        channel_name: Human-readable name of the channel.
        channel_str: API identifier string for the channel.
        ids: List of channel IDs that can be monitored.
        metrics: List of available metrics for this channel type.
        default_download: Default parameters for data download requests.

    """

    channel_name: str
    channel_str: str
    ids: list[int]
    metrics: list[MetricInfo]
    default_download: Optional[dict] = None

    @property
    def download_path(self):
        """
        Generate the API path for downloading performance data.

        Returns:
            str: API endpoint path for this channel type.

        """
        return f"perfmon_{self.channel_str}_stat"

    def download_payload(
        self, download: Optional[dict] = None, which_id: int = 1, down_metric: MetricInfo = MONITOR_METRIC.TE
    ):
        """
        Generate payload for data download requests.

        Args:
            download: Additional download parameters to include. Overrides any defaults
            which_id: Channel ID to download data from (default: 1).
            down_metric: Specific metric to download data for.

        Returns:
            dict: Complete payload for the download API request.

        """
        payload = {
            "chart_metric": "te",
            "action1": "savefile",
            "file_type": "0",  # 0 for UTC and 1 for TAI
            "chart_x_range": 600,
            f"chart_{self.channel_str}Id": which_id,
            f"{self.channel_str}_id": which_id,
            f"{self.channel_str}_ref": "GNSS",
            f"{self.channel_str}_status": "Monitoring",
            "down_metric": down_metric.metric_id,
            "ChannelName": self.channel_str,
            "reference_id": "1",
        }
        if self.default_download:
            payload = payload | self.default_download
        if download:
            payload = payload | download
        return payload


class DEFAULT_MONITOR_CONFIG:  # noqa: N801
    """
    Default monitoring configurations for all supported channel types.

    This class provides pre-configured MonitoringConfig instances for all
    supported channel types on TimeProvider 4100 devices, including GNSS,
    PPS, TOD, PTP, SyncE, T1/E1, and 10MHz channels.
    """

    GNSS = MonitoringConfig(
        channel_name="GNSS",
        channel_str="gnss",
        ids=[1],
        metrics=MONITOR_METRIC.TIME_ERROR,
        default_download={"chart_metric": "te"},
    )
    PPS = MonitoringConfig(
        channel_name="PPS",
        channel_str="pps",
        ids=[1, 2],
        metrics=MONITOR_METRIC.TIME_ERROR,
        default_download={"chart_metric": "te", "pps_ref": "Selected", "reference_id": "0"},
    )
    TOD = MonitoringConfig(
        channel_name="TOD",
        channel_str="tod",
        ids=[1, 2],
        metrics=MONITOR_METRIC.TIME_ERROR,
        default_download={"chart_metric": "te"},
    )
    PTP = MonitoringConfig(
        channel_name="PTP",
        channel_str="ptp",
        ids=[1, 2],
        metrics=MONITOR_METRIC.PTP,
        default_download={"chart_metric": "te", "reference_id": "1"},
    )
    SYNCE = MonitoringConfig(
        channel_name="SYNCE",
        channel_str="synce",
        ids=[1, 2],
        metrics=MONITOR_METRIC.TIME_INTERVAL,
        default_download={"chart_metric": "mtie_a", "chart_x_range": 1},
    )
    T1E1 = MonitoringConfig(
        channel_name="T1E1",
        channel_str="span",
        ids=[1, 2],
        metrics=MONITOR_METRIC.TIME_INTERVAL,
        default_download={"chart_metric": "mtie_a", "chart_x_range": 1},
    )
    TENMHZ = MonitoringConfig(
        channel_name="10MHZ",
        channel_str="tenMHz",
        ids=[1, 2],
        metrics=MONITOR_METRIC.TIME_INTERVAL,
        default_download={"chart_metric": "mtie_a", "chart_x_range": 1},
    )

    @classmethod
    def all(cls) -> list[MonitoringConfig]:
        """
        Get all available monitoring configurations.

        Returns:
            list[MonitoringConfig]: List of all configured channel monitoring setups.

        """
        return [attr for attr in cls.__dict__.values() if isinstance(attr, MonitoringConfig)]
