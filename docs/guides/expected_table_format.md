# Expected Table Format for write table

## locations
You must include name, lat and lon at minimum. Here are all the fields:
```yaml
name: "Lab A"  # Unique name for the location
lat: 35  # Latitude coordinate
lon: -84  # Longitude coordinate
projection: 4326  # Optional SRID/projection (defaults to 4326/WGS84)
public: true  # Optional boolean for public visibility. Defaults to `NULL`
```

If you want to update an existing location, you can either use the name or grab the uuid, both of these yamls would
update public to false with `opensampl load table locations --if-exists replace` 
```yaml
uuid: "entire-uuid-string"  
public: false  
```
```yaml
name: "Lab A" 
public: false  
```

## castdb.test_metadata
Tracks testing periods and experiments with start and end timestamps.

```yaml
name: "Test 1"  # Unique name for the test
start_date: "2024-01-01T00:00:00"  # Test start timestamp
end_date: "2024-01-07T00:00:00"  # Test end timestamp
```

## castdb.probe_metadata
Creation of minimal probe entries are automatically handled for new probes during `opensampl load [probe]`, which will
automatically detect probe_id, ip_address, vendor, and model. 

To assign other fields, use `opensampl load table probe_metadata`

To identify your probe, provide any of: 
* uuid
* Both probe_id and ip_address
* name, once set. 

```yaml
probe_id: "1-1"  # Probe identifier
ip_address: "0.0.0.0"  # IP address of the probe
name: "My Clock Probe"  # Optional Human-readable name 
public: true  # Optional boolean for public visibility, defaults: `NULL`
location_name: "Lab A" # Optional reference to the location name (will automatically fill location_uuid if location is in your locations table already)
test_name: "Test 1"  # Optional reference to test name (will automatically fill test_uuid if test is in your test_metadata table already)
```

To link a probe to a location, you can use either the location's name or uuid, so either: 
```yaml
location_name: "Unique Location Name"
location_uuid: "full-uuid-from-database"
```
The same is true for test: 
```yaml
test_name: "Unique Test Name"
test_uuid: "full-uuid-from-database"
```

openSAMPL will automatically resolve the uuid based on the name, and insert that into the probe_metadata table. 

## castdb.probe_data
Time series data from probes, storing timestamps and measured values. Insertion handled by `opensampl load [Probe]`.
If you truly needed to enter a time value manually, you must provide:
```yaml
time: "2024-01-01T00:00:00"  # Timestamp of measurement, without time zone
probe_uuid: "full-uuid-of-associated-probe"
value: 1.234e-09  # Measured value
```

## castdb.adva_metadata
ADVA-specific configuration and status information for probes. Insertion handled by `opensampl load ADVA`.
All of this information is included in the adva time files.

```yaml
probe_uuid: "full-uuid-from-database"
type: "Phase"  # Measurement type
start: "2024-01-01T00:00:00"  # Start time of probe
frequency: 1  # Sampling frequency
timemultiplier: 1  # Time multiplier
multiplier: 1  # Value multiplier
title: "ClockProbe1"  # Probe title
adva_probe: "ClockProbe"  # Probe type
adva_reference: "GPS"  # Reference source
adva_reference_expected_ql: "QL-NONE"  # Expected quality level
adva_source: "TimeClock"  # Source type
adva_direction: "NA"  # Direction
adva_version: 1.0  # Version number
adva_status: "RUNNING"  # Operating status
adva_mtie_mask: "G823-PDH"  # MTIE mask type
adva_mask_margin: 0  # Mask margin
```

## Multiple entries with one call
If you have many locations/probes/tests to add, you can do them all at once by simply making your yaml or json a list of dictionaries, 
where each dictionary item has the required fields outlined above. 

Insert both Lab A and Lab B, defined in my_labs.yaml below, with: `opensampl load table locations my_labs.yaml`
```yaml
- name: 'Lab A'
  lat: lata
  lon: lona
- name: 'Lab B'
  lat: latb
  lon: lonb
```

