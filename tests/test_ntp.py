"""Tests for the NTP probe and collectors."""

from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import call, patch

import pytest

from opensampl.vendors.constants import ProbeKey
from opensampl.vendors.ntp import NTPLocalCollector, NTPRemoteCollector, NtpProbe


class TestNTPLocalCollector:
    """Tests for local NTP collection helpers."""

    def test_collect_prefers_chrony_outputs(self):
        """Local collection should parse chrony output into probe metrics."""
        collector = NTPLocalCollector(
            target_host="127.0.0.1",
            collection_id="collector-host",
            collection_ip="10.0.0.5",
        )

        outputs = {
            ("chronyc", "tracking"): """
Reference ID    : GPS (time.cloudflare.com)
Stratum         : 2
System time     : 0.000000100 seconds slow of NTP time
Last offset     : +0.000000123 seconds
RMS offset      : 0.000001234 seconds
Leap status     : Normal
""",
            ("chronyc", "sources", "-v"): """
MS Name/IP address         Stratum Poll Reach LastRx Last sample
===============================================================================
* time.cloudflare.com            2   6   34   377   0.001   0.002   0.008
""",
            ("timedatectl", "show-timesync", "--all"): "System clock synchronized=yes\n",
            ("systemctl", "show", "systemd-timesyncd", "--property=ActiveState"): "ActiveState=active\n",
        }

        with patch.object(
            collector,
            "_run",
            side_effect=lambda cmd, timeout=8.0: outputs.get(tuple(cmd)),  # noqa: ARG005
        ):
            collector.collect()

        assert collector.offset_s == pytest.approx(1.23e-7)
        assert collector.jitter_s == pytest.approx(1.234e-6)
        assert collector.stratum == 2
        assert collector.reachability == 377
        assert collector.reference_id == "time.cloudflare.com"
        assert collector.sync_status == "tracking"
        assert collector.sync_health == 1.0
        assert collector.probe_id == "ntp-local"
        assert collector.observation_sources == [
            "chronyc_tracking",
            "chronyc_sources",
            "timedatectl",
            "systemctl_timesyncd",
        ]


class TestNTPRemoteCollector:
    """Tests for remote NTP collection helpers."""

    def test_collect_success_sets_metrics(self, monkeypatch: pytest.MonkeyPatch):
        """Remote collection should map ntplib responses onto collector fields."""
        response = SimpleNamespace(
            leap=0,
            stratum=3,
            poll=4,
            root_delay=0.125,
            root_dispersion=0.2,
            delay=0.05,
            offset=-0.002,
            ref_id=b"GPS",
            version=3,
        )

        client = SimpleNamespace(request=lambda *args, **kwargs: response)
        ntplib_mod = ModuleType("ntplib")
        ntplib_mod.NTPClient = lambda: client
        monkeypatch.setitem(__import__("sys").modules, "ntplib", ntplib_mod)

        collector = NTPRemoteCollector(
            target_host="time.cloudflare.com",
            target_port=123,
            timeout=1.5,
            collection_id="collector-host",
            collection_ip="10.0.0.5",
        )

        collector.collect()

        assert collector.sync_status == "synchronized"
        assert collector.sync_health == 1.0
        assert collector.stratum == 3
        assert collector.poll_interval_s == 16.0
        assert collector.root_delay_s == pytest.approx(0.125)
        assert collector.root_dispersion_s == pytest.approx(0.2)
        assert collector.delay_s == pytest.approx(0.05)
        assert collector.offset_s == pytest.approx(-0.002)
        assert collector.jitter_s == pytest.approx((0.05 * 0.05) + (0.25 * 0.2))
        assert collector.reference_id == "GPS"
        assert collector.leap_status == "no_warning"
        assert collector.probe_id == "remote:123"
        assert collector.observation_sources == ["ntplib"]
        assert collector.extras["version"] == 3

    def test_collect_failure_marks_probe_unreachable(self, monkeypatch: pytest.MonkeyPatch):
        """Remote collection should downgrade status cleanly on request errors."""

        class FailingClient:
            def request(self, *args, **kwargs):  # noqa: ARG002
                raise TimeoutError("timed out")

        ntplib_mod = ModuleType("ntplib")
        ntplib_mod.NTPClient = FailingClient
        monkeypatch.setitem(__import__("sys").modules, "ntplib", ntplib_mod)

        collector = NTPRemoteCollector(
            target_host="time.cloudflare.com",
            target_port=123,
            collection_id="collector-host",
            collection_ip="10.0.0.5",
        )

        collector.collect()

        assert collector.sync_status == "unreachable"
        assert collector.sync_health == 0
        assert collector.observation_sources == ["ntplib", "error"]
        assert collector.extras["error"] == "timed out"


class TestNtpProbe:
    """Tests for the NTP probe parser."""

    def test_process_metadata_sets_collection_and_target_probes(self, tmp_path: Path):
        """Processing file headers should register the collection probe and target probe."""
        ntp_file = tmp_path / "sample-ntp.csv"
        ntp_file.write_text(
            "\n".join(
                [
                    "# collection_ip: 10.0.0.5",
                    "# collection_id: collector-host",
                    "# target_host: time.cloudflare.com",
                    "# probe_id: public-time",
                    "# mode: remote",
                    "time,value,metric",
                    "2026-04-24T00:00:00Z,-0.001,phase_offset_s",
                ]
            )
            + "\n"
        )

        with patch("opensampl.vendors.ntp.load_probe_metadata") as mock_load_probe_metadata:
            probe = NtpProbe(ntp_file)
            metadata = probe.process_metadata()

        assert metadata["target_host"] == "time.cloudflare.com"
        assert probe.collection_probe == ProbeKey(ip_address="10.0.0.5", probe_id="collector-host")
        assert probe.probe_key == ProbeKey(ip_address="time.cloudflare.com", probe_id="public-time")
        mock_load_probe_metadata.assert_called_once_with(
            vendor=probe.vendor,
            probe_key=ProbeKey(ip_address="10.0.0.5", probe_id="collector-host"),
            data={"reference": True},
        )

    def test_load_metadata_registers_collection_probe_then_target_probe(self):
        """Metadata loading should create the collection reference before the target probe."""
        metadata = {
            "collection_ip": "10.0.0.5",
            "collection_id": "collector-host",
            "target_host": "time.cloudflare.com",
            "probe_id": "public-time",
            "mode": "remote",
        }
        probe_key = ProbeKey(ip_address="time.cloudflare.com", probe_id="public-time")

        with patch("opensampl.vendors.ntp.load_probe_metadata") as mock_load_probe_metadata:
            NtpProbe.load_metadata(probe_key=probe_key, metadata=metadata)

        assert mock_load_probe_metadata.call_args_list == [
            call(
                vendor=NtpProbe.vendor,
                probe_key=ProbeKey(ip_address="10.0.0.5", probe_id="collector-host"),
                data={"reference": True},
            ),
            call(vendor=NtpProbe.vendor, probe_key=probe_key, data=metadata),
        ]
