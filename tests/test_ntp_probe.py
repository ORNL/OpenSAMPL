"""Tests for NTP vendor, parsers, and snapshot format."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from opensampl.vendors.ntp import NtpProbe
from opensampl.vendors.ntp_parsing import _parse_chronyc_tracking, _parse_ntpq


def test_parse_chronyc_tracking_basic():
    text = """
Reference ID    : A1B2C3D4 (pool.ntp.org)
Stratum         : 3
Ref time (UTC)  : Thu Apr 11 12:00:00 2025
System time     : 0.000000100 seconds slow of NTP time
Last offset     : +0.000000050 seconds
RMS offset      : 0.000000200 seconds
Frequency       : 0.123 ppm slow
Residual freq   : 0.001 ppm
Skew            : 0.050 ppm
Root delay      : 0.010234 seconds
Root dispersion : 0.001000 seconds
Update interval : 64.0 seconds
"""
    p = _parse_chronyc_tracking(text)
    assert p["offset_s"] == pytest.approx(5e-8)
    assert p["jitter_s"] == pytest.approx(2e-7)
    assert p["stratum"] == 3


def test_parse_ntpq_line():
    text = """
     remote           refid      st t when poll reach   delay   offset  jitter
==============================================================================
*192.168.1.1     .GPS.       1 u   12   64   377    1.234    0.567    0.089
"""
    p = _parse_ntpq(text)
    assert p["offset_s"] == pytest.approx(0.000567)
    assert p["delay_s"] == pytest.approx(0.001234)
    assert p["stratum"] == 1


def test_ntp_probe_json_roundtrip(tmp_path: Path):
    doc = {
        "format_version": 1,
        "probe_id": "test-probe",
        "probe_ip": "127.0.0.1",
        "metadata": {
            "mode": "remote_server",
            "probe_name": "unit-test",
            "target_host": "pool.ntp.org",
            "target_port": 123,
            "sync_status": "synchronized",
            "leap_status": "no_warning",
            "stratum": 2,
            "reachability": 255,
            "offset_last_s": 0.001,
            "delay_s": 0.02,
            "jitter_s": 0.0001,
            "dispersion_s": None,
            "root_delay_s": 0.001,
            "root_dispersion_s": 0.0002,
            "poll_interval_s": 64.0,
            "reference_id": "GPS",
            "observation_source": "test",
            "collection_host": "",
            "additional_metadata": {},
        },
        "series": [
            {
                "time": datetime(2025, 4, 11, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
                "phase_offset_s": 0.001,
                "delay_s": 0.02,
                "jitter_s": 0.0001,
                "stratum": 2.0,
                "reachability": 255.0,
                "sync_health": 1.0,
            }
        ],
    }
    name = "ntp_127-0-0-1_test-probe_20250411T120000Z.json"
    fp = tmp_path / name
    fp.write_text(json.dumps(doc), encoding="utf-8")

    probe = NtpProbe(fp)
    assert probe.probe_key.probe_id == "test-probe"
    assert probe.probe_key.ip_address == "127.0.0.1"
    meta = probe.process_metadata()
    assert meta["mode"] == "remote_server"
    assert meta["stratum"] == 2
