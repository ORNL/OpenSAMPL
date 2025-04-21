# Create your own Probe Type
WARNING! This is an experimental tool, and may have breaking changes between release versions until it is marked as fully supported 

Clock types can be added to generate new ORMs for different clock types via skeleton files, which can then be further
configured to report the type of clock data that is being added to the database. 

It is recommended that you only use `opensampl create` with the package cloned down. See [Installation for developers](../getting-started/installation.md#installation-for-developers) for more details on how to do so.

## Usage

Command: `opensampl create <CONFIG PATH> [OPTIONS]` <br>
Arguments: 

* `CONFIG PATH`: The path to the config file defining the new probe type

Options:

* `--update-db` (`-u`):  Update the database with the new probe type

## Config File Formatting

`name`: The name of the probe type. Should not have spaces or special characters outside of `-` or `_`  <br>

`parser_class`: Optional: The name of the object that manages your probe type. By default, will be `f'{name.capitalize()}Probe'`<br>
`parser_module`: Optional: The module name for your probe type (ie, stem of the python file). By default, will be `name.lower()`<br>
`metadata_orm`: Optional: The name of the sqlalchemy ORM representation of the database table storing your probe type's metadata. By default, will be `f'{name.capitalize()}Metadata'`<br>
`metadata_table`: Optional: The table name that will store your probe type's metadata. By default, will be `f'{name.lower()}_metadata'`<br>

`metadata_fields`: A dictionary of metadata fields that will be provided for your new probe type. 

* The keys of this dict will be the names of the fields, and they will become columns in the dictionary table. 
* The values of the dict are optional, but when provided they are the SQLALCHEMY type of that field (defaults to `Text`) 


For a full example, this is the definition of the config that would create the (already existing) ADVA probe type.
```yaml
name: ADVA
parser_class: AdvaProbe
parser_module: adva
metadata_orm: AdvaMetadata
metadata_table: adva_metadata
metadata_fields:
  type:
  start: TIMESTAMP
  frequency: Integer
  timemultiplier: Integer
  multiplier: Integer
  title:
  adva_probe:
  adva_reference:
  adva_reference_expected_ql:
  adva_source:
  adva_direction:
  adva_version: Float
  adva_status:
  adva_mtie_mask:
  adva_mask_margin: Integer
```