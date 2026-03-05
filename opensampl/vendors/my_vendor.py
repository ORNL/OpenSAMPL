"""Probe implementation for My Vendor vendor"""

import pandas as pd

from opensampl.vendors.base_probe import BaseProbe
from opensampl.vendors.constants import ProbeKey, VENDORS
from opensampl.references import REF_TYPES
from opensampl.mixins.collect import CollectMixin

class MyVendorProbe(BaseProbe, CollectMixin):
    """Probe parser for My Vendor vendor data files"""

    vendor = VENDORS.MY_VENDOR

    def __init__(self, input_file: str, **kwargs):
        """Initialize MyVendorProbe from input file"""
        super().__init__(input_file)
        # TODO: parse self.input_file to extract self.probe_key
        # self.probe_key = ProbeKey(probe_id=..., ip_address=...)

    def process_metadata(self) -> dict:
        """
        Parse and return probe metadata from input file.

        Expected metadata fields:
		['serial_number',
		 'firmware_version',
		 'location',
		 'sample_rate_hz',
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
        Parse and load time series data from input file.

        Returns:
            pd.DataFrame with columns:
                - time (datetime64[ns]): timestamp for each measurement
                - value (float64): measured value at each timestamp
        """
        # TODO: implement time data parsing and call self.send_time_data(df, reference_type)
        # df = pd.DataFrame({"time": [...], "value": [...]})
        # self.send_time_data(df, reference_type=...)
        raise NotImplementedError

    def collect(self):
        # returns pd.DataFrame, then needs to get
        pass

    def save_to_file(self):
        # saves
        pass