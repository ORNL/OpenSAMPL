"""Tests for device-specific GPSD collection through gpspipe."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from opensampl.metrics import METRICS
from opensampl.mixins.collect import CollectMixin
from opensampl.references import REF_TYPES
from opensampl.vendors.gpsd import GPSDProbe

DOCUMENTED_TPV_PAYLOAD_FIELDS = {
    "mode",
    "altHAE",
    "altMSL",
    "ant",
    "antPwr",
    "climb",
    "clockbias",
    "clockdrift",
    "datum",
    "depth",
    "dgpsAge",
    "dgpsSta",
    "ecefx",
    "ecefy",
    "ecefz",
    "ecefpAcc",
    "ecefvx",
    "ecefvy",
    "ecefvz",
    "ecefvAcc",
    "epc",
    "epd",
    "eph",
    "eps",
    "ept",
    "epx",
    "epy",
    "epv",
    "geoidSep",
    "jam",
    "lat",
    "leapseconds",
    "lon",
    "magtrack",
    "magvar",
    "relD",
    "relE",
    "relN",
    "sep",
    "speed",
    "status",
    "temp",
    "track",
    "velD",
    "velE",
    "velN",
    "wanglem",
    "wangler",
    "wanglet",
    "wspeedr",
    "wspeedt",
    "wtemp",
}


def _artifacts_by_name(artifact: CollectMixin.CollectArtifact) -> dict[str, CollectMixin.DataArtifact]:
    """Index collected data artifacts by public metric name."""
    return {item.metric.name: item for item in artifact.data}


def test_tpv_mapping_covers_all_non_deprecated_payload_fields():
    """Every documented, non-deprecated TPV payload field has an explicit mapping."""
    assert set(GPSDProbe.TPV_METRICS) == DOCUMENTED_TPV_PAYLOAD_FIELDS
    assert GPSDProbe.TPV_METRICS["ept"] == METRICS.PHASE_OFFSET
    assert GPSDProbe.TPV_METRICS["mode"] == METRICS.SYNC_HEALTH
    assert GPSDProbe.TPV_METRICS["datum"].value_type is str
    assert GPSDProbe.TPV_METRICS["status"].value_type is int
    assert "alt" not in GPSDProbe.TPV_METRICS


def test_collect_maps_and_coalesces_selected_device_reports():
    """Collection scopes reports to the selected receiver and merges partial epochs."""
    reports = [
        {"class": "DEVICE", "driver": "wrong", "path": "/dev/ttyUSB1"},
        {"class": "DEVICE", "driver": "u-blox", "path": "/dev/ttyACM0"},
        {
            "class": "SKY",
            "device": "/dev/ttyACM0",
            "satellites": [{"used": True}, {"used": True}, {"used": False}],
        },
        {
            "class": "TPV",
            "device": "/dev/ttyACM0",
            "mode": 2,
            "time": "2026-07-15T12:00:00.000Z",
            "lat": 35.0,
            "alt": 999.0,
        },
        {
            "class": "TPV",
            "device": "/dev/ttyACM0",
            "mode": 3,
            "time": "2026-07-15T12:00:00.000Z",
            "lat": 35.93,
            "lon": -84.31,
            "ept": 0.005,
            "datum": "WGS84",
            "futureField": 123,
        },
        {
            "class": "TPV",
            "device": "/dev/ttyUSB1",
            "mode": 1,
            "time": "2026-07-15T12:00:01.000Z",
            "lat": 0.0,
        },
    ]
    output = "\n".join(json.dumps(report) for report in reports)
    config = GPSDProbe.CollectConfig(
        gpsd_host="gpsd.example",
        device="/dev/ttyACM0",
        duration=6,
    )

    with patch("opensampl.vendors.gpsd.subprocess.run", return_value=SimpleNamespace(stdout=output)) as run:
        artifact = GPSDProbe.collect(config)

    assert run.call_args.args[0] == ["gpspipe", "-w", "-n", "6", "gpsd.example:2947:/dev/ttyACM0"]
    assert artifact.probe_key.ip_address == "gpsd.example"
    assert artifact.probe_key.probe_id == "/dev/ttyACM0"
    assert artifact.metadata["device"] == "/dev/ttyACM0"
    assert artifact.metadata["driver"] == "u-blox"
    assert artifact.metadata["satellites_visible"] == 3
    assert artifact.metadata["satellites_used"] == 2

    artifacts = _artifacts_by_name(artifact)
    assert artifacts[METRICS.SYNC_HEALTH.name].value.to_dict("records") == [
        {"time": "2026-07-15T12:00:00.000Z", "value": 1.0}
    ]
    assert artifacts[METRICS.LATITUDE.name].value.iloc[0]["value"] == pytest.approx(35.93)
    assert artifacts[METRICS.LONGITUDE.name].value.iloc[0]["value"] == pytest.approx(-84.31)
    assert artifacts[METRICS.PHASE_OFFSET.name].value.iloc[0]["value"] == pytest.approx(0.005)
    assert artifacts[METRICS.DATUM.name].value.iloc[0]["value"] == "WGS84"
    assert all(item.reference_type == REF_TYPES.GNSS for item in artifact.data)


def test_collect_formats_ipv6_and_ignores_nonfinite_values():
    """IPv6 selectors are bracketed and invalid floating-point samples are omitted."""
    reports = '{"class":"TPV","mode":1,"lat":NaN}\n'
    config = GPSDProbe.CollectConfig(gpsd_host="2001:db8::1", device="/dev/gps0", duration=1)
    with patch("opensampl.vendors.gpsd.subprocess.run", return_value=SimpleNamespace(stdout=reports)) as run:
        artifact = GPSDProbe.collect(config)

    assert run.call_args.args[0][-1] == "[2001:db8::1]:2947:/dev/gps0"
    assert [item.metric for item in artifact.data] == [METRICS.SYNC_HEALTH]
    assert artifact.data[0].value.iloc[0]["value"] == 0.0


def test_collect_requires_selected_device_tpv_report():
    """TPV data from a different daemon device cannot satisfy collection."""
    reports = '{"class":"TPV","device":"/dev/gps1","mode":3}\n'
    with (
        patch("opensampl.vendors.gpsd.subprocess.run", return_value=SimpleNamespace(stdout=reports)),
        pytest.raises(RuntimeError, match="no TPV reports.*gps0"),
    ):
        GPSDProbe.collect(GPSDProbe.CollectConfig(device="/dev/gps0", duration=1))


def test_file_round_trip_preserves_all_metrics(tmp_path: Path):
    """Serialized GPSD artifacts reload metadata and each TPV metric independently."""
    reports = (
        '{"class":"TPV","device":"/dev/gps0","mode":3,'
        '"time":"2026-07-15T12:00:00Z","ept":0.001,"status":3}\n'
    )
    with patch("opensampl.vendors.gpsd.subprocess.run", return_value=SimpleNamespace(stdout=reports)):
        artifact = GPSDProbe.collect(GPSDProbe.CollectConfig(device="/dev/gps0", duration=1))

    path = tmp_path / "GPSDProbe_sample.txt"
    path.write_text(GPSDProbe.create_file_content(artifact))
    probe = GPSDProbe(path)

    metadata = probe.process_metadata()
    assert metadata["device"] == "/dev/gps0"
    assert metadata["additional_metadata"]["source"] == "gpspipe"
    assert probe.probe_key.probe_id == "/dev/gps0"

    with patch.object(probe, "send_data") as send_data:
        probe.process_time_data()
    assert {call.kwargs["metric"].name for call in send_data.call_args_list} == {
        METRICS.SYNC_HEALTH.name,
        METRICS.PHASE_OFFSET.name,
        METRICS.FIX_STATUS.name,
    }
