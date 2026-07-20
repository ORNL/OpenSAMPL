# Create your own Probe Type

This workflow is still experimental. It is useful when you want to scaffold a new vendor /
probe family inside a local clone of the repository.

## Recommended setup

1. Clone the repository locally.
2. Install OpenSAMPL in the development environment.
3. Run `opensampl sdk template probe.yaml` to create a starter configuration.
4. Edit `probe.yaml` for the new clock probe type.
5. Run `opensampl sdk create probe.yaml` to generate the scaffold. Include the
   `--collect-mixin` flag to prefill the collection functions.
6. Fill in the generated parser, metadata model, and any collector mixins you need.
7. Run `opensampl init` or include `--update-db` when running `opensampl sdk create`
   to create the new tables in the database.

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

Create a starter configuration without replacing an existing file:

`opensampl sdk template <CONFIG PATH>`

Generate a probe scaffold from the edited configuration:

`opensampl sdk create <CONFIG PATH> [OPTIONS]`

The original `opensampl create <CONFIG PATH> [OPTIONS]` command remains available
as a compatibility alias.

Arguments:

* `CONFIG PATH`: The path to the config file defining the new probe type

Options:

* `--update-db` (`-u`): Update the database with the new probe type
* `--collect-mixin` (`-c`): Include a shell for implementing probe collection

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

`metadata_fields`: A list of metadata fields that will be provided for your new probe type.

* Each entry has a required `name`, which becomes a column in the generated metadata table.
* Each entry can have an optional `type`, which defaults to `Text` when omitted.


For a concrete example, this is the configuration that would scaffold the existing ADVA
probe type:
```yaml
name: ADVA
parser_class: AdvaProbe
parser_module: adva
metadata_orm: AdvaMetadata
metadata_table: adva_metadata
metadata_fields:
  - name: type
  - name: start
    type: TIMESTAMP
  - name: frequency
    type: Integer
  - name: timemultiplier
    type: Integer
  - name: multiplier
    type: Integer
  - name: title
  - name: adva_probe
  - name: adva_reference
  - name: adva_reference_expected_ql
  - name: adva_source
  - name: adva_direction
  - name: adva_version
    type: Float
  - name: adva_status
  - name: adva_mtie_mask
  - name: adva_mask_margin
    type: Integer
```
