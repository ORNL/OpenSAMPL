# OpenSAMPL Collect API Guide

The OpenSAMPL collect API provides tools for collecting data from timing measurement devices, including Microchip TWST (Two-Way Satellite Time and Frequency Transfer) modems and TimeProvider® 4100 devices. This guide explains how to use both the CLI interface and the programmatic API.

## Overview

The collect API enables automated collection of measurement data from network-connected timing devices. Currently supported devices:

- **Microchip TWST Modems** (ATS6502 series): Collect offset and EBNO tracking values along with contextual information
- **Microchip TimeProvider® 4100** (TP4100): Collect timing performance metrics from various input channels via web interface

## CLI Usage

### Installation

The collect functionality is included with the main OpenSAMPL installation:

```bash
pip install opensampl
```

### Basic CLI Commands

The collect CLI is accessed through the `opensampl-collect` command:

```bash
# View available collection tools
opensampl-collect --help

# View microchip device options
opensampl-collect microchip --help

# View TWST modem specific options
opensampl-collect microchip twst --help

# View TP4100 device specific options
opensampl-collect microchip tp4100 --help
```

### Collecting from Microchip TWST Modems

The basic command structure for collecting from TWST modems:

```bash
opensampl-collect microchip twst --ip <MODEM_IP_ADDRESS>
```

#### Required Parameters

- `--ip`: IP address of the TWST modem

#### Optional Parameters

- `--control-port`: Control port of the modem (default: 1700)
- `--status-port`: Status port of the modem (default: 1900)
- `--dump-interval`: Duration between file dumps in seconds (default: 300 = 5 minutes)
- `--total-duration`: Total duration to run in seconds (default: run indefinitely)
- `--output-dir`: Output directory for CSV files (default: ./output)

#### Recommended usage
Due to telnet connections being a little finicky, it is recommended that users use the `--total-duration` parameter and have some sort of overarching manager to run repeatedly. It's commonly been found that the "indefinite" mode stops collecting (with no error coming from the telnet connection) after roughly 24 hours. 

For example, with a cronjob as follows
```bash
*/5 * * * * opensampl-collect microchip twst --ip 192.168.1.100 --output-dir microchip-twst-readings --total-duration 310 --dump-interval 310 >> /home/vj7/twst-collect-logs/$(date +\%Y_\%V).log 2>&1
```
Where the collection duration/dump interval is slightly longer than the repeat (here, 5 minutes and 10 seconds for the collections and repeating every 5 minutes) to account for any delays in connection/startup and avoid missed readings. 

#### Examples

Basic collection (runs indefinitely, saves every 5 minutes):
```bash
opensampl-collect microchip twst --ip 192.168.1.100
```

Customized collection with specific timing:
```bash
opensampl-collect microchip twst --ip 192.168.1.100 \
  --dump-interval 600 \
  --total-duration 3600 \
  --output-dir /data/collections
```

Collection with custom ports:
```bash
opensampl-collect microchip twst --ip 10.0.9.15 \
  --control-port 1700 \
  --status-port 1900
```

### Collecting from Microchip TimeProvider® 4100 (TP4100)

The TP4100 collector connects to devices via their web interface and collects timing performance metrics from various input channels.

Accoding to the TP4100 guide, the webinterface is created automatically when the modem is setup, no additional configuration needed. If you have access to the ip-address from your device, you can view the webpage at [https://<ip-address>]() in a browser (the https is important, it will not connect at http). 

If you need to portforward, you will need to forward port 443 (the default https port)

The basic command structure for collecting from TP4100 devices:

```bash
opensampl-collect microchip tp4100 --host <DEVICE_IP_ADDRESS>
```

#### Required Parameters

- `--host` or `-h`: IP address or hostname of the TP4100 device

#### Optional Parameters

- `--port` or `-p`: HTTPS port for connection (default: 443)
- `--output-dir` or `-o`: Directory for collected data (default: ./output)
- `--duration` or `-d`: Duration in seconds for data collection (default: 600)
- `--channels` or `-c`: Specific channels to collect from (can be specified multiple times)
- `--metrics` or `-m`: Specific metrics to collect (can be specified multiple times)
- `--method`: Collection method - "chart_data" or "download_file" (default: chart_data)
- `--save-full-status`: Save full status information as JSON
- `--verbose` or `-v`: Enable debug logging

#### Collection Methods

**Chart Data Method** (default):
- Downloads chart data for the specified duration period
- Shows the same data visible on the device's Status Page chart
- Configurable time window (duration parameter)

**Download File Method**:
- Downloads data files directly from the device
- Typically contains the last 24 hours of data
- Same endpoint as the "Save as" button on Status Page

#### Available Channels

The TP4100 supports monitoring multiple input channel types:

- **GNSS**: GPS timing reference
- **PPS**: Pulse Per Second inputs (1, 2)
- **TOD**: Time of Day inputs (1, 2) 
- **PTP**: Precision Time Protocol inputs (1, 2)
- **SYNCE**: Synchronous Ethernet inputs (1, 2)
- **T1E1**: T1/E1 span timing inputs (1, 2)
- **10MHZ**: 10MHz frequency reference inputs (1, 2)

#### Available Metrics

**Time Error Metrics**:
- `te`: Time error (ns)
- `cte`: Constant time error (ns)
- `max-te`: Maximum time error (ns)

**PTP-Specific Metrics** (PTP channels only):
- `floor_fwd`: Floor Forward (ns)
- `floor_rev`: Floor Reverse (ns)
- `fpp1_fwd`: FPP1 Forward (%)
- `fpp1_rev`: FPP1 Reverse (%)
- `fpp2_fwd`: FPP2 Forward (%)
- `fpp2_rev`: FPP2 Reverse (%)

**Time Interval Metrics** (SYNCE, T1E1, 10MHZ channels):
- `mtie`: MTIE (ns)
- `tdev`: TDEV
- `tdev_p`: TDEV w/ Population
- `tie`: TIE

#### Examples

Basic collection from all monitored channels:
```bash
opensampl-collect microchip tp4100 --host 192.168.1.100
```

Collect specific channels with longer duration:
```bash
opensampl-collect microchip tp4100 --host 192.168.1.100 \
  --duration 3600 \
  --channels GNSS \
  --channels PPS-1
```

Collect specific metrics with custom output directory:
```bash
opensampl-collect microchip tp4100 --host 192.168.1.100 \
  --metrics te \
  --metrics cte \
  --output-dir /data/tp4100_collections
```

Download 24-hour data files:
```bash
opensampl-collect microchip tp4100 --host 192.168.1.100 \
  --method download_file \
  --save-full-status \
  --verbose
```

## Programmatic API

For integration into scripts or applications, you can use the collect API directly:

### TWST Modem API

#### Basic Usage

```python
from opensampl.collect.microchip.twst.generate_twst_files import collect_files

# Collect data programmatically
collect_files(
    host="192.168.1.100",
    dump_interval=600,
    total_duration=3600,
    output_dir="/data/collections"
)
```

### Function Parameters

The `collect_files` function accepts the following parameters:

- `host` (str): IP address or hostname of the modem
- `control_port` (int, optional): Control port for modem (default: 1700)
- `status_port` (int, optional): Status port for modem (default: 1900)  
- `output_dir` (str, optional): Directory path where CSV files will be saved (default: "./output")
- `dump_interval` (int, optional): Duration in seconds between each data collection cycle (default: 300)
- `total_duration` (int, optional): Total runtime in seconds. If None, runs indefinitely (default: None)

### Advanced Usage Example

```python
import asyncio
from opensampl.collect.microchip.twst.context import ModemContextReader
from opensampl.collect.microchip.twst.readings import ModemStatusReader
from opensampl.collect.microchip.twst.generate_twst_files import collect_data

async def custom_collection():
    # Create readers for different data types
    status_reader = ModemStatusReader(
        host="192.168.1.100", 
        duration=60,  # collect for 1 minute
        port=1900
    )
    
    context_reader = ModemContextReader(
        host="192.168.1.100", 
        prompt="TWModem-32>",
        port=1700
    )
    
    # Collect data concurrently
    await collect_data(status_reader, context_reader)
    
    # Access collected data
    measurements = status_reader.readings
    context_info = context_reader.result
    
    return measurements, context_info

# Run the collection
measurements, context = asyncio.run(custom_collection())
```

### TP4100 API

#### Basic Usage

```python
from opensampl.collect.microchip.tp4100.collect_4100 import main as collect_tp4100

# Collect data from TP4100 device
collect_tp4100(
    host="192.168.1.100",
    duration=3600,
    output_dir="/data/tp4100_collections"
)
```

#### Function Parameters

The TP4100 `main` function accepts the following parameters:

- `host` (str): IP address or hostname of the TP4100 device
- `port` (int, optional): HTTPS port for connection (default: 443)
- `output_dir` (str, optional): Directory for collected data (default: "./output")
- `duration` (int, optional): Duration in seconds for data collection (default: 600)
- `channels` (list[str], optional): Specific channels to collect from (default: all monitored)
- `metrics` (list[str], optional): Specific metrics to collect (default: all available)
- `method` (Literal["chart_data", "download_file"], optional): Collection method (default: "chart_data")
- `save_full_status` (bool, optional): Save full status information as JSON (default: False)

#### Advanced Usage Example

```python
from opensampl.collect.microchip.tp4100.collect_4100 import TP4100Collector

# Create collector instance for custom data collection
collector = TP4100Collector(
    host="192.168.1.100",
    port=443,
    output_dir="/data/custom_collections",
    duration=1800,  # 30 minutes
    channels=["GNSS", "PPS-1", "PTP-1"],
    metrics=["te", "cte", "max-te"],
    method="chart_data",
    save_full_status=True
)

try:
    # Get list of monitored channels
    monitored_channels = collector.get_monitored_channels()
    print(f"Currently monitored channels: {monitored_channels}")
    
    # Collect readings
    collector.collect_readings()
    print("Data collection completed successfully")
    
except Exception as e:
    print(f"Collection failed: {e}")
finally:
    collector.session.close()
```

#### Environment Configuration

TP4100 authentication credentials can be configured via environment variables:

```bash
# Set authentication credentials (optional - defaults to factory settings)
export TP4100__USERNAME=admin
export TP4100__PASSWORD=Microchip
export TP4100__HOST=192.168.1.100
export TP4100__PORT=443
```

Or using a `.env` file:
```
TP4100__USERNAME=admin
TP4100__PASSWORD=Microchip
TP4100__HOST=192.168.1.100
TP4100__PORT=443
```

## Output Format

### CSV Files

The collect API generates timestamped CSV files containing:

1. **YAML metadata header**: Context information about the collection including:
   - Collection timestamp
   - Device information (host, metric, input channel)
   - Collection method and parameters
   
2. **CSV data**:
   - TP4100 -  Two columns*:
      - `timestamp`: When the measurement was taken
      - `value`: The measured value
   - TWST - Three columns: 
     - `timestamp`
     - `reading`
     - `value`
   
\* TP4100 has slightly different csv formatting when outputting from `file_download` mode, depending on specific reading type 

### Example Output Files

#### TWST Modem Output

File: `192.168.1.100_6502-Modem_2025-08-19T10:30:15.123456Z.csv`

```csv
# timestamp: 2025-08-19T10:30:15.123456Z
# local:
#   sid: STATION_A
#   prn: 123
#   ip: 192.168.1.100
#   lat: 35.9311256
#   lon: -84.3292469
# remotes:
#   ch1:
#     rx_channel: ch1
#     sid: STATION_B  
#     prn: 456
#     lat: 36.1627
#     lon: -86.7816

timestamp,reading,value
1724932215123,offset_tracking,1.234e-09
1724932215124,ebno_tracking,45.6
```

#### TP4100 Output

File: `192.168.1.100_TP4100_gnss-1_te_2025-08-19T10:30:15.123456Z.csv`

```csv
# Title: TP4100 Performance Monitor
# metric: time-error (ns)
# host: 192.168.1.100
# input: GNSS-1
# start_time: 2025-08-19T10:00:00.000000Z
# method: chart_data
# alarm_thresh: 1000
# channelStatus: Monitoring
# reference: GNSS

timestamp,value
2025-08-19T10:00:00.000000+00:00,125.4
2025-08-19T10:01:00.000000+00:00,132.7
2025-08-19T10:02:00.000000+00:00,118.9
```

## Connection Requirements

### TWST Modem Connectivity

- The collecting system must have network access to the target modem
- Default ports:
  - Control port: 1700 (for commands and context data)
  - Status port: 1900 (for measurement readings)

### TWST Modem Configuration  

- TWST modem must be configured for remote access
- Command prompt should be set appropriately (default: "TWModem-32>")
- Status output should be enabled on the status port

### TP4100 Connectivity

- The collecting system must have HTTPS network access to the TP4100 device
- Default port: 443 (HTTPS web interface)
- SSL/TLS certificate verification is disabled (self-signed certificates accepted)

### TP4100 Configuration

- TP4100 web interface must be enabled and accessible
- Authentication credentials required (defaults to factory settings):
  - Username: admin
  - Password: Microchip
- Performance monitoring must be enabled on desired channels
- Channels must be configured with appropriate references and thresholds

## Error Handling

The collect API includes robust error handling:

- **Connection failures**: Automatic retry with exponential backoff
- **Maximum retry attempts**: Stops after 5 consecutive failures  
- **Timeout handling**: Configurable timeout for network operations
- **Graceful shutdown**: Handles keyboard interrupts (Ctrl+C)

### Monitoring Collection Status

The API provides logging output showing:
- Connection status
- Number of readings collected per cycle
- File output locations
- Error conditions and retry attempts

## Troubleshooting

### Common Issues

#### TWST Modem Issues

1. **Connection refused**: 
   - Verify modem IP address and network connectivity
   - Check firewall settings on both systems
   - Confirm modem ports are configured correctly

2. **No data collected**:
   - Verify modem is generating status output
   - Check that status port is accessible
   - Ensure modem time synchronization is active

#### TP4100 Issues

1. **HTTPS connection failures**:
   - Verify TP4100 IP address and network connectivity
   - Confirm HTTPS port 443 is accessible
   - Check that web interface is enabled on the device
   - Verify SSL/TLS is not being blocked by firewall

2. **Authentication failures**:
   - Confirm username/password credentials
   - Check if credentials have been changed from factory defaults
   - Verify environment variables are set correctly (if using)

3. **No monitored channels found**:
   - Ensure performance monitoring is enabled on desired channels
   - Verify channels are configured with appropriate references
   - Check channel status in device web interface

4. **Empty data collections**:
   - Verify channels are actively monitoring (status: "Monitoring" or "OK")
   - Check that timing references are connected and stable
   - Ensure sufficient duration for meaningful data collection

#### General Issues

5. **Permission errors**:
   - Verify write permissions to output directory
   - Check disk space availability

### Debug Options

Enable detailed logging to troubleshoot issues:

```python
import logging
logging.getLogger('opensampl.collect').setLevel(logging.DEBUG)
```

For CLI usage, the logging level is controlled by the OpenSAMPL configuration system.

## Integration with OpenSAMPL Database

Once data is collected, you can load it into the OpenSAMPL database using the standard load commands. The collect API is designed to generate data files that are compatible with the OpenSAMPL data loading system.

See the main OpenSAMPL documentation for details on loading collected data into the database.