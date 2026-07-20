"""Tests for GPS/GNSS collection through gpspipe."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from opensampl.metrics import METRICS
from opensampl.references import REF_TYPES
from opensampl.vendors.gnss import GnssProbe


def test_collect_maps_gpspipe_json_to_artifact():
    reports = [
        {"class": "DEVICE", "driver": "u-blox", "path": "/dev/ttyACM0"},
        {
            "class": "SKY",
            "satellites": [{"used": True}, {"used": True}, {"used": False}],
        },
        {
            "class": "TPV",
            "device": "/dev/ttyACM0",
            "mode": 3,
            "time": "2026-07-15T12:00:00.000Z",
            "lat": 35.93,
            "lon": -84.31,
            "altHAE": 260.5,
        },
    ]
    output = "\n".join(json.dumps(report) for report in reports)
    config = GnssProbe.CollectConfig(ip_address="gpsd.example", probe_id="roof-gnss", duration=3)

    with patch("opensampl.vendors.gnss.subprocess.run", return_value=SimpleNamespace(stdout=output)) as run:
        artifact = GnssProbe.collect(config)

    assert run.call_args.args[0] == ["gpspipe", "-w", "-n", "3", "gpsd.example:2947"]
    assert artifact.probe_key.probe_id == "roof-gnss"
    assert artifact.metadata["fix_mode"] == 3
    assert artifact.metadata["satellites_visible"] == 3
    assert artifact.metadata["satellites_used"] == 2
    assert artifact.metadata["latitude"] == pytest.approx(35.93)
    assert artifact.data[0].metric == METRICS.SYNC_HEALTH
    assert artifact.data[0].reference_type == REF_TYPES.GNSS
    assert artifact.data[0].value.iloc[0]["value"] == 1.0


def test_collect_requires_tpv_report():
    with patch(
        "opensampl.vendors.gnss.subprocess.run",
        return_value=SimpleNamespace(stdout='{"class":"VERSION"}\n'),
    ):
        with pytest.raises(RuntimeError, match="no TPV"):
            GnssProbe.collect(GnssProbe.CollectConfig(duration=1))


def test_file_round_trip_metadata(tmp_path):
    reports = '{"class":"TPV","mode":2,"time":"2026-07-15T12:00:00Z"}\n'
    with patch("opensampl.vendors.gnss.subprocess.run", return_value=SimpleNamespace(stdout=reports)):
        artifact = GnssProbe.collect(GnssProbe.CollectConfig(probe_id="receiver-1", duration=1))

    path = tmp_path / "GnssProbe_sample.txt"
    path.write_text(GnssProbe.create_file_content(artifact))
    probe = GnssProbe(path)

    metadata = probe.process_metadata()
    assert metadata["probe_id"] == "receiver-1"
    assert metadata["additional_metadata"]["source"] == "gpspipe"
    assert probe.probe_key.probe_id == "receiver-1"
