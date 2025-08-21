# Random Data Generation

The `opensampl load random` command allows you to generate synthetic test data for all supported probe types. This is useful for testing, development, and demonstration purposes.

The data will be uploaded to your database in whichever way is configured with opensampl config, as with any load command.

## Usage

```bash
opensampl load random <PROBE_TYPE> [OPTIONS]
```

Where `<PROBE_TYPE>` can be any supported vendor:
- `ADVA` - ADVA clock probes
- `MicrochipTWST` - Microchip TWST modems
- `MicrochipTP4100` - Microchip TP4100 GPS receivers

## Basic Examples

Generate data for a single ADVA probe with default settings:
```bash
opensampl load random adva
```

Generate data for multiple probes:
```bash
opensampl load random adva --num-probes 5
```

Generate 24 hours of data with specific parameters:
```bash
opensampl load random adva --duration 24 --sample-interval 0.5
```

## Configuration Options

### Basic Parameters

| Option  | Type | Default | Description |
|--------|---|---------|-------------|
| `--num-probes` | int | 1       | Number of probes to generate data for |
| `--duration` | float | 1.0     | Duration of data in hours |
| `--seed` | int | None    | Random seed for reproducible results |
| `--sample-interval` | float | 1.0     | Sample interval in seconds |

### Time Series Parameters

| Option | Type | Description |
|--------|------|-------------|
| `--base-value` | float | Base value for time offset measurements |
| `--noise-amplitude` | float | Noise amplitude/standard deviation |
| `--drift-rate` | float | Linear drift rate per second |
| `--outlier-probability` | float | Probability of outliers per sample (default: 0.01) |
| `--outlier-multiplier` | float | Multiplier for outlier noise amplitude (default: 10.0) |

### Probe Identity Parameters

| Option | Type | Description                                         |
|--------|------|-----------------------------------------------------|
| `--probe-ip` | str | Specific IP address for the probe (randomly generated if not provided) |
| `--probe-id` | str | Specific probe ID (available for ADVA and MicrochipTP4100; randomly generated/incremented if not provided) |

### Microchip TWST Specific Parameters

| Option | Type | Description |
|--------|------|-------------|
| `--num-channels` | int | Number of remote channels to generate data for (default: 4) |
| `--ebno-base-value` | float | Base value for Eb/No measurements in dB |
| `--ebno-noise-amplitude` | float | Noise amplitude/standard deviation for Eb/No measurements in dB |
| `--ebno-drift-rate` | float | Linear drift rate per second for Eb/No measurements in dB/s |

## Configuration Files

You can use YAML configuration files to specify complex parameters, which are all named identically to the cli options:

```bash
opensampl load random adva --config my_test_config.yaml
```

Example configuration file (`test_config.yaml`):
```yaml
# Basic settings
num_probes: 3
duration_hours: 2.0
seed: 42

# Time series parameters
sample_interval: 0.5
base_value: 1.5e-7
noise_amplitude: 2.3e-9
drift_rate: -5.2e-13
outlier_probability: 0.02
outlier_multiplier: 15.0
```

Command-line options take precedence over configuration file values.

## How It Works

### Data Generation Process

1. **Probe Identity**: Each probe is assigned a unique combination of IP address and probe ID
   - IP addresses are randomly generated in the format `X.X.X.X` if not specified
   - Probe IDs are automatically incremented (1, 2, 3...) if not specified, or based on the provided probe ID for multiple probes

2. **Time Series Generation**: Creates realistic time offset measurements with:
   - **Base Value**: Starting offset value (vendor-specific defaults)
   - **Linear Drift**: Systematic change over time 
   - **Random Noise**: Gaussian noise around the drift line
   - **Outliers**: Occasional large deviations for realism

3. **Database Storage**: 
   - Probe metadata is automatically generated and stored
   - Time series data is sent directly to the database
   - All data uses appropriate database schemas for each vendor

### Vendor-Specific Defaults

Each probe type has realistic default values:

**ADVA Probes:**
- Base value: Random between -1µs to 1µs
- Noise amplitude: Random between 1ns to 10ns  
- Drift rate: Random between -1e-12 to 1e-12 s/s

**Microchip TWST Modems:**
- Base value: Random between -10ns to 10ns 
- Noise amplitude: Random between 0.1ns to 1ns
- Drift rate: Random between -1e-12 to 1e-12 s/s
- Eb/No base value: Random between 10.0 to 20.0 dB
- Eb/No noise amplitude: Random between 0.5 to 2.0 dB
- Eb/No drift rate: Random between -0.01 to 0.01 dB/s
- Default channels: 4 remote channels
- Fixed probe ID: "modem"

**Microchip TP4100 GPS:**
- Base value: Random between -500ns to 500ns
- Noise amplitude: Random between 10ns to 50ns  
- Drift rate: Random between -1e-10 to 1e-10 s/s
- Measurement type: "time-error (ns)" vs GNSS reference
- Supports custom probe IDs

### Reproducibility

Use the `--seed` parameter for reproducible data:
```bash
# These commands will generate identical data
opensampl load random adva --seed 123 --num-probes 2
opensampl load random adva --seed 123 --num-probes 2
```

When generating multiple probes with a seed, each probe gets a unique but deterministic seed (original + probe index).

## Advanced Usage

### Multiple Probe Types
Generate data for different vendors:
```bash
# Generate ADVA data
opensampl load random adva --num-probes 2 --duration 12

# Generate Microchip TWST data  
opensampl load random twst --num-probes 3 --duration 8

# Generate TP4100 GPS data
opensampl load random tp4100 --num-probes 1 --duration 24
```

### High-Frequency Data
Generate high-resolution data:
```bash
opensampl load random adva --duration 0.1 --sample-interval 0.01 --num-probes 1
```
This creates 6 minutes of data sampled every 10ms (36,000 samples).

### Testing Scenarios
Create specific test scenarios:
```bash
# High drift scenario
opensampl load random adva --drift-rate 1e-10 --duration 24

# High noise scenario  
opensampl load random adva --noise-amplitude 1e-6 --outlier-probability 0.1

# Stable reference scenario
opensampl load random adva --drift-rate 0 --noise-amplitude 1e-12 --outlier-probability 0
```

### Microchip TWST Examples
Generate TWST modem data with specific parameters:
```bash
# Generate data for 8 channels with high Eb/No
opensampl load random twst --num-channels 8 --ebno-base-value 25.0 --duration 12

# Low Eb/No scenario with more noise
opensampl load random twst --ebno-base-value 12.0 --ebno-noise-amplitude 3.0 --ebno-drift-rate -0.05

# Multiple probes with specific configuration
opensampl load random twst --num-probes 3 --num-channels 6 --duration 4
```

### Microchip TP4100 Examples
Generate TP4100 GPS receiver data:
```bash
# Generate data with specific probe ID
opensampl load random tp4100 --probe-id "GPS-Site-A" --duration 24

# High precision scenario
opensampl load random tp4100 --base-value 0 --noise-amplitude 5e-9 --drift-rate 0

# Multiple GPS receivers
opensampl load random tp4100 --num-probes 5 --probe-id "GPS-Array" --duration 48
```

## Output

After successful generation, you'll see a summary:
```
=== Generated 3 ADVA probes ===
  - 192.168.1.100:1
  - 10.0.0.85:2  
  - 172.16.42.200:3
```

The generated data is immediately available in your database and can be accessed through the regular openSAMPL APIs and analysis tools.