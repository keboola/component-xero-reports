import dataclasses
import json
from dataclasses import dataclass, asdict
from typing import List

import dataconf


class ConfigurationBase:

    @staticmethod
    def _convert_private_value(value: str):
        return value.replace('"#', '"pswd_')

    @staticmethod
    def _convert_private_value_inv(value: str):
        if value and value.startswith('pswd_'):
            return value.replace('pswd_', '#', 1)
        else:
            return value

    @classmethod
    def load_from_dict(cls, configuration: dict):
        """
        Initialize the configuration dataclass object from dictionary.
        Args:
            configuration: Dictionary loaded from json configuration.

        Returns:

        """
        json_conf = json.dumps(configuration)
        json_conf = ConfigurationBase._convert_private_value(json_conf)
        return dataconf.loads(json_conf, cls, ignore_unexpected=True)

    @classmethod
    def get_dataclass_required_parameters(cls) -> List[str]:
        """
        Return list of required parameters based on the dataclass definition (no default value)
        Returns: List[str]

        """
        return [cls._convert_private_value_inv(f.name) for f in dataclasses.fields(cls)
                if f.default == dataclasses.MISSING
                and f.default_factory == dataclasses.MISSING]

    @classmethod
    def as_dict(cls, obj) -> dict:
        """Return dataclass as dictionary."""
        return asdict(obj)


@dataclass
class ReportParameters(ConfigurationBase):
    date: str
    periods: int
    timeframe: str
    tracking_option_id1: str
    tracking_option_id2: str
    standard_layout: bool = True
    payments_only: bool = False


@dataclass
class SyncOptions(ConfigurationBase):
    previous_periods: int = 0


@dataclass
class Destination(ConfigurationBase):
    load_type: str = "full_load"


@dataclass
class Configuration(ConfigurationBase):
    report_parameters: ReportParameters
    sync_options: SyncOptions
    destination: Destination
    tenant_ids: str = ""
