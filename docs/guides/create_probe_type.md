# Create your own Probe Type

This workflow is still experimental. It is useful when you want to scaffold a new vendor /
probe family inside a local clone of the repository.

## Recommended setup

1. Clone the repository locally.
2. Install OpenSAMPL in the development environment.
3. Run `opensampl create` to generate the scaffold.
4. Fill in the generated parser, metadata model, and any collector mixins you need.
5. Run `opensampl init` or `opensampl create --update-db ...` to create the new tables in the database.

```bash
git clone git@github.com:ORNL/OpenSAMPL.git
cd OpenSAMPL
uv venv
uv sync --all-extras --dev
source .venv/bin/activate
```

If you plan to contribute the new probe type back to the repository, you will also need to
add any required schema or migration updates alongside the generated code.

## Usage

Command: `opensampl create <CONFIG PATH> [OPTIONS]`

Arguments:

* `CONFIG PATH`: The path to the config file defining the new probe type

Options:

* `--update-db` (`-u`): Update the database with the new probe type

## Config File Formatting

`name`: The name of the probe type. It should not contain spaces or special characters
outside of `-` or `_`.

`parser_class`: Optional. The class name for the probe implementation. By default it is
`f'{name.capitalize()}Probe'`.

`parser_module`: Optional. The Python module name for your probe type. By default it is
`name.lower()`.

`metadata_orm`: Optional. The SQLAlchemy ORM class name for the metadata table. By default
it is `f'{name.capitalize()}Metadata'`.

`metadata_table`: Optional. The database table name for the metadata table. By default it is
`f'{name.lower()}_metadata'`.

`metadata_fields`: A dictionary of metadata fields that will be provided for your new probe type.

* The keys become column names in the generated metadata table.
* The values are optional SQLAlchemy type names. If omitted, the field defaults to `Text`.


For a concrete example, this is the configuration that would scaffold the existing ADVA
probe type:
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
