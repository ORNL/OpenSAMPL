"""Probe implementation for NTP2 vendor"""

import pandas as pd

from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import ProbeKey, VENDORS
from opensampl.references import REF_TYPES
from opensampl.mixins.collect import CollectMixin

class NtpProbe2(BaseProbe, CollectMixin):
    """Probe parser for NTP2 vendor data files"""

    vendor = VENDORS.NTP2

    class CollectConfig(CollectMixin.CollectConfig):
        """
        The following configuration fields are inherited from the Collect mixin.
        Change the defaults by uncommenting and changing value

        Add additional fields, which will automatically be added to the collect click options
        and provided to calls to collect
        output_dir: Optional[Path] = None
        load: bool = False
        duration: int = 300

        ip_address: str = '127.0.0.1'
        probe_id: str = '1-1'
        """


    def __init__(self, input_file: str, **kwargs):
        """Initialize NtpProbe2 from input file"""
        super().__init__(input_file)
        # TODO: parse self.input_file to extract self.probe_key
        # self.probe_key = ProbeKey(probe_id=..., ip_address=...)

    def process_metadata(self) -> dict:
        """
        Parse and return probe metadata from input file.

        Expected metadata fields:
		['mode',
		 'probe_name',
		 'target_host',
		 'target_port',
		 'sync_status',
		 'leap_status',
		 'stratum',
		 'reachability',
		 'offset_last_s',
		 'delay_s',
		 'jitter_s',
		 'dispersion_s',
		 'root_delay_s',
		 'root_dispersion_s',
		 'poll_interval_s',
		 'reference_id',
		 'observation_source',
		 'collection_host',
		 'additional_metadata']

        Returns:
            dict with metadata field names as keys
        """
        # TODO: implement metadata parsing
        # return {
        #     "field_name": value,
        #     ...
        # }
        raise NotImplementedError

    def process_time_data(self) -> pd.DataFrame:
        """
        Parse and load time series data from self.input_file.

        Use either send_time_data (which prefills METRICS.PHASE_OFFSET)
        or send_data and provide alternative METRICS type.
        Both require a df as follows:
            pd.DataFrame with columns:
                - time (datetime64[ns]): timestamp for each measurement
                - value (float64): measured value at each timestamp


        """
        # TODO: implement time data parsing and call self.send_time_data(df, reference_type)
        #                                       or self.send_data(df, metric_type, reference_type)
        # df = pd.DataFrame({"time": [...], "value": [...]})
        # self.send_time_data(df, reference_type=...)

        # Ensure the format it is reading in matches that in save_to_file
        raise NotImplementedError

    @classmethod
    def collect(cls, collect_config: CollectConfig) -> CollectMixin.CollectArtifact:
        """
            Create a collect artifact defined as follows
            class CollectArtifact(BaseModel):
                data: pd.DataFrame
                metric: MetricType = METRICS.UNKNOWN
                reference_type: ReferenceType = REF_TYPES.UNKNOWN
                compound_reference: Optional[dict[str, Any]] = None
                probe_key: Optional[ProbeKey] = None
                metadata: Optional[dict] = Field(default_factory=dict)

            on a collect_config.load, the metadata and data will be loaded into db.

            define logic for the save_to_file as well.
        """
        # TODO: implement the logic for creating a CollectArtifact, as above.
        #

        raise NotImplementedError

    @classmethod
    def create_file_content(cls, collected: CollectMixin.CollectArtifact) -> str:
        # TODO: Create the str content for an output file. Ensure readable by parse functions & that required metadata is available
        #  Filename will be automatically generated as {ip_address}_{probe_id}_{vendor}_{timestamp}.txt and saved to directory provided by cli
        raise NotImplementedError





