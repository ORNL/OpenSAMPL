"""
Collection script for Microchip TimeProvider® 4100 Devices

This tool utilizes the web interface that is accessible at the IP address of the device.
See the user guide for how to configure access to the web interface.
"""

import sys
import textwrap
import warnings
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat
from typing import Any, Literal, Optional

import pandas as pd
import requests
import yaml
from loguru import logger
from urllib3.exceptions import InsecureRequestWarning

from opensampl.collect.microchip.tp4100 import DEFAULT_MONITOR_CONFIG, MetricInfo, MonitoringConfig
from opensampl.config.tp4100 import TP4100Config

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    UTC = timezone.utc

warnings.filterwarnings("ignore", category=InsecureRequestWarning)


class TP4100Collector:
    """
    Collector class for Microchip TimeProvider 4100 device data.

    This class provides functionality to collect time and performance data from
    Microchip TP4100 devices via their web interface.
    """

    def __init__(
        self,
        host: str,
        port: int = 443,
        output_dir: str = "./output",
        duration: int = 600,
        channels: Optional[list[str]] = None,
        metrics: Optional[list[str]] = None,
        method: Literal["chart_data", "download_file"] = "chart_data",
        save_full_status: bool = False,
    ):
        """
        Initialize TP4100Collector.

        Args:
            host: IP address or hostname of the TP4100 device.
            port: Port number for HTTPS connection (default: 443).
            output_dir: Directory path where collected data will be saved.
            duration: Duration in seconds for data collection.
            channels: List of specific channels to collect data from.
            metrics: List of specific metrics to collect.
            method: Collection method - "chart_data" downloads chart data for
                   specified duration (data showing in chart on Status Page),
                   "download_file" downloads last 24 hours (same as "Save as").
            save_full_status: Whether to save full status information.

        """
        self.config = TP4100Config(HOST=host, PORT=port)
        self.session = requests.Session()
        self.session.verify = False
        self.duration = duration
        self.metrics = metrics
        self.channels = channels
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.save_full_status = save_full_status

        self.login()
        self.method = method

        self.start_time = datetime.now(UTC)
        self.output_dir = Path(output_dir).resolve()
        logger.info(f"Saving to {self.output_dir}")

    def login(self):
        """
        Authenticate with the TP4100 device web interface.

        Raises:
            Exception: If login fails or connection issues occur.

        """
        login_url = f"{self.config.url}/login"
        login_data = {"txtuname": self.config.USERNAME, "txtpasswd": self.config.PASSWORD, "action": "applylogin"}
        try:
            resp = self.session.post(login_url, data=login_data, headers=self.headers)
            resp.raise_for_status()
        except Exception as e:
            logger.exception(f"Error trying to login to {login_url}; {e}")
            raise

    def get_monitored_channels(self):
        """
        Retrieve list of currently monitored channels from the device.

        Returns:
            set: Set of channel names that are currently being monitored.

        Raises:
            Exception: If unable to retrieve channel information.

        """
        channel_url = f"{self.config.url}/channels_thresholdValue"
        data = {"tgrp": -1}
        try:
            resp = self.session.post(channel_url, data=data, headers=self.headers)
            resp.raise_for_status()

            channel_data = resp.json()

            if self.save_full_status:
                filename = self.get_filename(detail="channelStatus", extension=".json")
                new_file = self.output_dir / filename
                self.output_dir.mkdir(parents=True, exist_ok=True)
                new_file.write_text(resp.text)

            return {
                x.get("monitorChannelString")
                for x in channel_data
                if x.get("monitorChStatusString", "").lower() in ("monitoring", "ok")
            }
        except Exception as e:
            logger.exception(f"Error trying to get channel information from {channel_url}; {e}")
            raise

    def collect_readings(self):
        """
        Collect readings from configured channels and metrics.

        Determines which channels to monitor (either specified or all monitored),
        then collects data for each requested metric using the configured method.
        """
        monitored_channels = self.get_monitored_channels()

        channels = monitored_channels if self.channels is None else self.channels

        channels = {x.lower() for x in channels}

        readings_to_collect = []
        for mon_con in DEFAULT_MONITOR_CONFIG.all():
            for ch_id in mon_con.ids:
                if (
                    any(x.startswith(f"{mon_con.channel_name}-{ch_id}".lower()) for x in channels)
                    or mon_con.channel_name.lower() in channels
                ):
                    readings_to_collect.extend([(mon_con, ch_id, metric) for metric in mon_con.metrics])

        for request_tpl in readings_to_collect:
            mon_ch, ch_id, metr = request_tpl
            ch_name = mon_ch.channel_name
            if self.metrics is not None and metr.short_name not in self.metrics:
                logger.trace(f"Skipping metric: {ch_name}; {ch_id}; {metr.full_name}")
                continue

            logger.debug(f"Requesting metric: {ch_name}; {ch_id}; {metr.full_name}")

            if self.method == "chart_data":
                self.collect_chart_data(request_tpl)
            elif self.method == "download_file":
                self.download_files(request_tpl)

    def get_filename(self, detail: Optional[str] = None, extension: str = ".txt"):
        """
        Generate timestamped filename for probe connection

        Format (no detail): {host}_TP4100_{timestamp}.{extension}
        Format (with detail): {host}_TP4100_{detail}_{timestamp}.{extension}

        Args:
            detail: Optional string to include in filename.
            extension: File extension to use (default: '.txt').

        Returns:
            str: Generated filename with timestamp and optional metric info.

        """
        filename = f"{self.config.HOST}_TP4100"
        if detail is not None:
            filename += f"_{detail}"
        cleaned_ext = f".{extension.lstrip('.')}"
        filename += f"_{datetime.now(UTC).replace(tzinfo=None).isoformat()}{cleaned_ext}"
        return filename

    def collect_chart_data(
        self, request_key: tuple[MonitoringConfig, int, MetricInfo], download_dict: Optional[dict[str, Any]] = None
    ):
        """
        Collect chart data for a specific metric and channel.

        Requests chart data from the device's web interface for the specified
        duration and saves it as a CSV file with YAML metadata headers.

        Args:
            request_key: Tuple of (monitor_config, channel_id, metric).
            download_dict: Optional additional request data to further configure API call\

        Raises:
            Exception: If data collection or file writing fails.

        """

        def format_utc_second(tai_sec: str, utc_offset: str) -> datetime:
            return datetime.fromtimestamp(int(tai_sec) - int(utc_offset), UTC)

        mon_ch, ch_id, metr = request_key
        ch_name = mon_ch.channel_name

        request_data = {
            "metric": metr.short_name.lower(),
            "xRange": self.duration,
            "tStart": -1,
            "channelName": ch_name.lower(),
            "channelId": ch_id,
        }

        if download_dict is not None:
            request_data.update(download_dict)

        chart_data_url = f"{self.config.url}/get_chart_data"
        chart_resp = self.session.post(chart_data_url, data=request_data, headers=self.headers)
        try:
            chart_resp.raise_for_status()
        except Exception:
            logger.error(pformat(request_data))
            logger.exception(chart_resp.text)
            raise
        data = chart_resp.json()

        df = pd.DataFrame(data["chartData"])
        if len(df) > 0:
            df["timestamp"] = df.apply(lambda r: format_utc_second(r["X"], r["OFFSET"]), axis=1)
            df = df[["timestamp", "Y"]].rename(columns={"Y": "value"})
            data_start = df["timestamp"].min().isoformat()
        else:
            data_start = None

        headers = {
            "Title": "TP4100 Performance Monitor",
            "metric": metr.full_name,
            "host": self.config.HOST,
            "input": f"{ch_name}-{ch_id}",
            "start_time": data_start,
            "method": "chart_data",
        }
        headers.update({k: v for k, v in data.items() if k in ("alarm_thresh", "channelStatus", "reference")})

        logger.debug(f"Collected {len(df)} values starting at {data_start}")
        header_str = yaml.safe_dump(headers, sort_keys=False)
        header_str = textwrap.indent(header_str, prefix="# ")
        file_detail = f"{ch_name.lower()}-{ch_id}_{metr.short_name.lower()}"
        filename = self.get_filename(detail=file_detail, extension=".csv")

        new_file = self.output_dir / filename
        self.output_dir.mkdir(parents=True, exist_ok=True)

        with new_file.open("w") as f:
            f.write(header_str)

        df.to_csv(new_file, mode="a", index=False)

    def download_files(
        self, request_key: tuple[MonitoringConfig, int, MetricInfo], download_dict: Optional[dict[str, Any]] = None
    ):
        """
        Download data files directly from the device.

        Downloads data files (typically last 24 hours) directly from the device,
        similar to using "Save as" on the Status Page.

        Args:
            request_key: Tuple of (monitor_config, channel_id, metric).
            download_dict: Optional download configuration parameters.

        Raises:
            Exception: If download or file saving fails.

        """
        mon_ch, ch_id, metr = request_key
        payload = mon_ch.download_payload(which_id=ch_id, down_metric=metr, download=download_dict)
        url = f"{self.config.url}/{mon_ch.download_path}"
        logger.debug(yaml.safe_dump(payload, sort_keys=False))

        resp = self.session.post(url, data=payload, headers=self.headers)
        resp.raise_for_status()
        try:
            filename = resp.headers.get("content-disposition").split("attachment; filename=", maxsplit=1)
            filename = next((x for x in filename if x != ""), None)
            new_file = self.output_dir / filename
            timestamp = datetime.fromtimestamp(int(new_file.stem[-10:]), UTC)

            self.output_dir.mkdir(parents=True, exist_ok=True)

            headers = {
                "Start": timestamp.isoformat(),
                "host": self.config.HOST,
                "metric": metr.full_name,
                "method": "download_file",
            }

            file_content = resp.text.splitlines()
            while len(file_content) > 0 and file_content[0].startswith("#"):
                curline = file_content.pop(0).lstrip("#")
                key, val = curline.split(": ", maxsplit=1)
                if key.strip() == "Title":
                    title_val, rest = val.split("(", maxsplit=1)
                    headers[key.strip()] = title_val
                    metr_str, inner_info = rest.split("):", maxsplit=1)
                    headers.update(
                        {k.strip(): v for k, v in (x.split(" = ", maxsplit=1) for x in inner_info.split(", "))}
                    )
                else:
                    headers[key.strip()] = val
            header_str = yaml.safe_dump(headers, sort_keys=False)
            header_str = textwrap.indent(header_str, prefix="# ")
            with new_file.open("w") as f:
                f.write(header_str)
                f.writelines("\n".join(file_content))

        except Exception:
            file_detail = f"{mon_ch.channel_name.lower()}-{ch_id}_{metr.short_name.lower()}"
            filename = self.get_filename(detail=file_detail)
            new_file = self.output_dir / filename
            self.output_dir.mkdir(parents=True, exist_ok=True)
            new_file.write_bytes(resp.content)


def main(
    host: str,
    port: int = 443,
    output_dir: str = "./output",
    duration: int = 600,
    channels: Optional[list[str]] = None,
    metrics: Optional[list[str]] = None,
    method: Literal["chart_data", "download_file"] = "chart_data",
    save_full_status: bool = False,
):
    """
    Collect time data from Microchip TimeProvider 4100 devices.

    This tool connects to TP4100 devices via their web interface and collects
    performance metrics and time data.
    """
    collector = TP4100Collector(
        host=host,
        port=port,
        output_dir=output_dir,
        duration=duration,
        channels=channels,
        metrics=metrics,
        method=method,
        save_full_status=save_full_status,
    )

    try:
        collector.collect_readings()
        logger.info("Data collection completed successfully")
    except Exception as e:
        logger.debug(f"{e}", exc_info=True)
        logger.error(f"Collection failed: {e}")
        raise
    finally:
        collector.session.close()
