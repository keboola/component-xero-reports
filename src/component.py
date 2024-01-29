import csv
import json
import logging
from typing import Dict, List, Union
from datetime import datetime
from dateutil import parser

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException
from keboola.component.interface import register_csv_dialect
from keboola.utils.helpers import comma_separated_values_to_list
from xero_python.accounting import RowType
from xero_python.models import serialize_to_dict

from xero.client import XeroClient
from xero.utility import XeroException
from xero_python.accounting.models import report as XeroReport


# configuration variables
KEY_TENANT_IDS = 'tenant_ids'
KEY_GROUP_SYNC_OPTIONS = 'sync_options'
KEY_DATE = 'date'
KEY_PERIODS = 'periods'
KEY_TIMEFRAME = 'timeframe'
KEY_TRACKING_OPTION_ID1 = 'tracking_option_id1'
KEY_TRACKING_OPTION_ID2 = 'tracking_option_id2'
KEY_STANDARD_LAYOUT = 'standard_layout'
KEY_PAYMENTS_ONLY = 'payments_only'
KEY_GROUP_DESTINATION_OPTIONS = 'destination'
KEY_LOAD_TYPE = 'load_type'

KEY_STATE_OAUTH_TOKEN_DICT = "#oauth_token_dict"
KEY_STATE_ENDPOINT_COLUMNS = "endpoint_columns"

# list of mandatory parameters => if some is missing,
# component will fail with readable message on initialization.
REQUIRED_PARAMETERS = [KEY_GROUP_SYNC_OPTIONS, KEY_GROUP_DESTINATION_OPTIONS]


class Component(ComponentBase):
    def __init__(self, data_path_override: str = None):
        self.incremental_load = None
        self.client = None
        self.tables = {}
        self._writer_cache = {}
        self.new_state = {}
        super().__init__(data_path_override=data_path_override, required_parameters=REQUIRED_PARAMETERS)

        register_csv_dialect()

    def run(self):
        params: Dict = self.configuration.parameters
        # sync_options = params.get(KEY_GROUP_SYNC_OPTIONS, {})
        destination = params.get(KEY_GROUP_DESTINATION_OPTIONS, {})

        """
        date = sync_options.get(KEY_DATE)
        periods = sync_options.get(KEY_PERIODS)
        timeframe = sync_options.get(KEY_TIMEFRAME)
        tracking_option_id1 = sync_options.get(KEY_TRACKING_OPTION_ID1)
        tracking_option_id2 = sync_options.get(KEY_TRACKING_OPTION_ID2)
        standard_layout = sync_options.get(KEY_STANDARD_LAYOUT)
        payments_only = sync_options.get(KEY_PAYMENTS_ONLY)
        """

        load_type = destination.get(KEY_LOAD_TYPE, "full_load")
        self.incremental_load = load_type == "incremental_load"

        self._init_client()

        available_tenant_ids = self._get_available_tenant_ids()
        tenant_ids_to_download = self._get_tenants_to_download(available_tenant_ids)

        self.download_report(tenant_ids=tenant_ids_to_download)
        self.refresh_token_and_save_state()

    def refresh_token_and_save_state(self) -> None:
        self._refresh_client_token()
        self.new_state[KEY_STATE_OAUTH_TOKEN_DICT] = json.dumps(self.client.get_xero_oauth2_token_dict())
        self.write_state_file(self.new_state)

    def _refresh_client_token(self) -> None:
        try:
            self.client.force_refresh_token()
        except XeroException as xero_exc:
            raise UserException("Failed to authorize the component. Please reauthorize the component. "
                                "\n Due to the functioning of the XERO authorization, if a component fails,"
                                " the component must be reauthorized.") from xero_exc

    def download_report(self, tenant_ids: List[str], **kwargs) -> None:
        logging.info(f"Fetching report data for tenant_ids: {tenant_ids}")
        for tenant_id in tenant_ids:
            report = self.client.get_balance_sheet_report(tenant_id=tenant_id, **kwargs)
            parsed = self.parse_balance_sheet(report)
            table_name = f"balance_sheet_{tenant_id}"

            header = ['report_id', 'updated_date_utc', 'section_title', 'cell_1', 'cell_2', 'cell_3']
            table_def = self.create_out_table_definition(table_name,
                                                         columns=header,
                                                         primary_key=['updated_date_utc', 'cell_2'],
                                                         incremental=self.incremental_load)

            with open(table_def.full_path, 'w', newline='') as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerows(parsed)

            self.write_manifest(table_def)

    def _init_client(self) -> None:
        logging.info("Authorizing Client")

        state = self.get_state_file()
        state_authorization_params = state.get(KEY_STATE_OAUTH_TOKEN_DICT)

        if self._state_contains_authorization_parameters(state_authorization_params):
            logging.info("Authorizing Client from state")
            self._init_client_from_state(state_authorization_params)
        else:
            logging.info("Authorizing Client from oauth")
            self._init_client_from_config()
        logging.info("Client Authorized")

    def _init_client_from_state(self, state_authorization_params: Union[str, Dict]) -> None:
        oauth_credentials = self.configuration.oauth_credentials
        self.write_state_file({"test": str(oauth_credentials)})
        exit(0)
        oauth_credentials.data = self._load_state_oauth(state_authorization_params)
        self.client = XeroClient(oauth_credentials)
        try:
            self.refresh_token_and_save_state()
            self.client.get_available_tenant_ids()
        except (UserException, XeroException):
            logging.warning("Authorizing Client from state failed, trying from oauth")
            self._init_client_from_config()

    @staticmethod
    def _load_state_oauth(state_authorization_params: Union[str, Dict]) -> Dict:
        if isinstance(state_authorization_params, str):
            return json.loads(state_authorization_params)
        elif isinstance(state_authorization_params, dict):
            return state_authorization_params
        else:
            raise UserException("Invalid state, please contact support")

    def _init_client_from_config(self) -> None:
        oauth_credentials = self.configuration.oauth_credentials
        if isinstance(oauth_credentials.data.get("scope"), str):
            oauth_credentials.data["scope"] = oauth_credentials.data["scope"].split(" ")
        self.client = XeroClient(oauth_credentials)
        try:
            self.refresh_token_and_save_state()
            self.client.get_available_tenant_ids()
        except (UserException, XeroException) as xero_exception:
            raise UserException(xero_exception) from xero_exception

    @staticmethod
    def _state_contains_authorization_parameters(state_authorization_params: Dict) -> bool:
        if state_authorization_params:
            if "access_token" in state_authorization_params and "scope" in state_authorization_params \
                    and "expires_in" in state_authorization_params and "token_type" in state_authorization_params:
                return True
        return False

    def _get_available_tenant_ids(self) -> List[str]:
        try:
            return self.client.get_available_tenant_ids()
        except XeroException as xero_exc:
            raise UserException from xero_exc

    def _get_tenants_to_download(self, available_tenant_ids: List[str]) -> List[str]:
        tenant_ids_to_download = comma_separated_values_to_list(self.configuration.parameters.get(KEY_TENANT_IDS))

        if not tenant_ids_to_download:
            tenant_ids_to_download = available_tenant_ids
            logging.info(f'Tenant IDs not specified, using all available: {available_tenant_ids}.')

        self._validate_tenants_to_download(tenant_ids_to_download, available_tenant_ids)
        return tenant_ids_to_download

    @staticmethod
    def _validate_tenants_to_download(tenant_ids_to_download: List[str], available_tenant_ids: List[str]) -> None:
        unavailable_tenants = set(tenant_ids_to_download) - set(available_tenant_ids)
        if unavailable_tenants:
            unavailable_tenants_str = ', '.join(unavailable_tenants)
            raise UserException(f"Some tenants to be downloaded (IDs: {unavailable_tenants_str})"
                                f" are not accessible, please, check if you granted sufficient credentials.")

    def parse_balance_sheet(self, data: dict):
        report = serialize_to_dict(self.convert_api_response(data))
        rows = []
        for section in report.rows:
            if section.row_type == RowType.SECTION:
                title = section.title

                for row in section.rows:
                    if row.row_type == RowType.ROW or row.row_type == RowType.SUMMARYROW:
                        cells = [cell.value for cell in row.cells]
                        rows.append([report.report_id, report.updated_date_utc, title, *cells])

        return rows

    @staticmethod
    def convert_api_response(api_data):
        report_data = api_data[0]  # Assuming the API response is a list with a single report

        my_report = XeroReport

        my_report.report_id = report_data.report_id if hasattr(report_data, 'report_id') else ''
        my_report.report_name = report_data.report_name if hasattr(report_data, 'report_name') else ''
        my_report.report_type = report_data.report_type if hasattr(report_data, 'report_type') else ''
        my_report.report_title = report_data.report_title if hasattr(report_data, 'report_title') else ''
        my_report.report_date = parser.parse(report_data.report_date).strftime('%Y-%m-%d') if (
            hasattr(report_data, 'report_date')) else ''
        my_report.updated_date_utc = report_data.updated_date_utc if (
            hasattr(report_data, 'updated_date_utc')) else datetime.utcnow()

        rows_data = report_data.rows if hasattr(report_data, 'rows') else []

        my_report.rows = [row for row in rows_data]

        return my_report


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = Component()
        comp.execute_action()
    except UserException as exc:
        logging.warning("During the component fail, the authorization is invalidated due to the functioning of the "
                        "XERO authorization. If The authorization is invalid, you must reauthorize the component")
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
