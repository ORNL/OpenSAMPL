"""Probe-type loading, option forwarding, and command validation."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from opensampl.cli import cli, collect, load, random
from opensampl.config.base import BaseConfig
from opensampl.mixins.collect import CollectMixin
from opensampl.mixins.random_data import RandomDataMixin
from opensampl.vendors.constants import VENDORS

VENDORS_TO_TEST = VENDORS.all()


@pytest.fixture
def runner(tmp_path):
    config = BaseConfig(_env_file=tmp_path / ".env", ARCHIVE_PATH=tmp_path / "archive")
    with patch("opensampl.cli.load_config", return_value=config):
        yield CliRunner()


@pytest.mark.parametrize("vendor", VENDORS_TO_TEST, ids=lambda v: v.name)
def test_probe_type_help(runner, vendor):
    assert not load.commands[vendor.name].deprecated
    result = runner.invoke(cli, ["load", vendor.name, "--help"])
    assert result.exit_code == 0, result.output
    assert "deprecated" not in result.output.lower()


@pytest.mark.parametrize("vendor", VENDORS_TO_TEST, ids=lambda v: v.name)
@pytest.mark.parametrize("directory", [False, True])
@pytest.mark.parametrize("options", [[], ["-m", "-n", "-w", "2", "-c", "7", "-p"], ["-t"]])
def test_probe_type_dispatch_and_options(runner, tmp_path, vendor, directory, options):
    source = tmp_path / "input"
    if directory:
        source.mkdir()
    else:
        source.write_text("sample")
    parser = vendor.get_parser()
    method = "_process_directory" if directory else "_process_file"
    with patch.object(parser, method) as process:
        result = runner.invoke(cli, ["load", vendor.name.swapcase(), str(source), *options])
        assert result.exit_code == 0, result.output
        process.assert_called_once()
        config = process.call_args.args[0]
    assert "DeprecationWarning" not in result.output
    assert config.filepath == source
    assert config.metadata is ("-t" not in options)
    assert config.time_data is ("-m" not in options)
    assert config.no_archive is ("-n" in options)
    assert config.max_workers == (2 if "-w" in options else 4)
    assert config.chunk_size == (7 if "-c" in options else None)
    assert config.show_progress is ("-p" in options)


@pytest.mark.parametrize(
    "arguments",
    [
        ["load", "unknown"],
        ["load", "ADVA"],
        ["load", "ADVA", "/nonexistent/probe-input"],
        ["load", "ADVA", "--invalid-option"],
    ],
)
def test_invalid_probe_invocations(runner, arguments):
    result = runner.invoke(cli, arguments)
    assert result.exit_code == 2
    assert "Error:" in result.output


def test_load_help_and_unaffected_command_registration(runner):
    result = runner.invoke(cli, ["load", "--help"])
    assert result.exit_code == 0
    assert "probe" not in load.commands
    for vendor in VENDORS_TO_TEST:
        assert vendor.name in result.output
        parser = vendor.get_parser()
        assert (vendor.name in random.commands) is issubclass(parser, RandomDataMixin)
        assert (vendor.name in collect.commands) is issubclass(parser, CollectMixin)
    assert "deprecated" not in result.output.lower()
    assert load.commands["random"] is random
    assert "table" in load.commands
