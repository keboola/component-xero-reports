import json
import logging
from typing import Dict, List, Union
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dateutil import parser

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException
from keboola.component.interface import register_csv_dialect
from keboola.utils.helpers import comma_separated_values_to_list
from keboola.csvwriter import ElasticDictWriter

from xero_python.accounting import RowType
from xero_python.models import serialize_to_dict

from xero.client import XeroClient
from xero.utility import XeroException
from xero_python.accounting.models import report as XeroReport


# configuration variables
KEY_TENANT_IDS = 'tenant_ids'
KEY_GROUP_REPORT_PARAMS = 'report_parameters'
KEY_GROUP_SYNC_OPTIONS = 'sync_options'
KEY_PREVIOUS_PERIODS = 'previous_periods'
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
REQUIRED_PARAMETERS = [KEY_GROUP_REPORT_PARAMS, KEY_GROUP_DESTINATION_OPTIONS]


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
        report_params = params.get(KEY_GROUP_REPORT_PARAMS, {})
        sync_options = params.get(KEY_GROUP_SYNC_OPTIONS, {})
        destination = params.get(KEY_GROUP_DESTINATION_OPTIONS, {})

        load_type = destination.get(KEY_LOAD_TYPE, "full_load")
        self.incremental_load = load_type == "incremental_load"

        self._init_client()

        available_tenant_ids = self._get_available_tenant_ids()
        tenant_ids_to_download = self._get_tenants_to_download(available_tenant_ids)

        batches = self.generate_batches(report_params, sync_options)

        for batch in batches:
            self.download_report(tenant_ids=tenant_ids_to_download, **batch)

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

            table_def = self.create_out_table_definition(table_name,
                                                         columns=[],
                                                         primary_key=[],
                                                         incremental=self.incremental_load)

            with ElasticDictWriter(table_def.full_path, []) as wr:
                wr.writeheader()
                wr.writerows(parsed)

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

    def parse_balance_sheet(self, data: dict) -> list:
        report = serialize_to_dict(self.convert_api_response(data))
        results = []
        for section in report.rows:
            if section.row_type == RowType.SECTION:
                title = section.title

                for row in section.rows:
                    result = {}
                    if row.row_type == RowType.ROW or row.row_type == RowType.SUMMARYROW:
                        _cells = [cell.value for cell in row.cells]
                        _attributes = [cell.attributes for cell in row.cells]

                        counter = 1
                        for attribute_list in _attributes:
                            if attribute_list:
                                for attribute in attribute_list:
                                    result[f"attribute_id_{counter}"] = attribute.id
                                    result[f"attribute_value_{counter}"] = attribute.value
                                    counter += 1

                        result.update({
                            'report_title': report.report_title,
                            'report_date': report.report_date,
                            'updated_date_utc': report.updated_date_utc,
                            'section_title': title,
                        })

                        result.update({f"cell_{c}": value if len(_cells) > 0 else '' for c, value in enumerate(_cells)})

                        results.append(result)

        return results

    @staticmethod
    def convert_api_response(api_data):
        report_data = api_data[0]  # Assuming the API response is a list with a single report

        my_report = XeroReport

        my_report.report_id = report_data.report_id if hasattr(report_data, 'report_id') else ''
        my_report.report_name = report_data.report_name if hasattr(report_data, 'report_name') else ''
        my_report.report_type = report_data.report_type if hasattr(report_data, 'report_type') else ''
        report_titles = report_data.report_titles if hasattr(report_data, 'report_titles') else ''
        report_title = ' - '.join(report_titles).strip()
        my_report.report_title = report_title if report_title else ''

        my_report.report_date = parser.parse(report_data.report_date).strftime('%Y-%m-%d') if (
            hasattr(report_data, 'report_date')) else ''
        my_report.updated_date_utc = report_data.updated_date_utc if (
            hasattr(report_data, 'updated_date_utc')) else datetime.utcnow()

        rows_data = report_data.rows if hasattr(report_data, 'rows') else []

        my_report.rows = [row for row in rows_data]

        return my_report

    @staticmethod
    def generate_dates(base_date, timeframe, periods) -> list:
        base_date = datetime.strptime(base_date, "%Y-%m-%d")

        date_list = []

        if timeframe == "MONTH":
            step = relativedelta(months=1)
        elif timeframe == "QUARTER":
            step = relativedelta(months=3)
        elif timeframe == "YEAR":
            step = relativedelta(years=1)
        else:
            raise UserException("Invalid timeframe. Choose from MONTH, QUARTER, or YEAR.")

        date_list.append(base_date.strftime("%Y-%m-%d"))

        for _ in range(periods):
            base_date -= step
            # Adjust the day to the last day of the month
            last_day_of_month = base_date.replace(day=1) + timedelta(days=32)
            last_day_of_month = last_day_of_month.replace(day=1) - timedelta(days=1)
            date_list.append(last_day_of_month.strftime("%Y-%m-%d"))

        return date_list

    def generate_batches(self, report_params: dict, sync_options) -> list:
        batches = []
        dates = self.generate_dates(report_params[KEY_DATE], report_params[KEY_TIMEFRAME],
                                    sync_options[KEY_PREVIOUS_PERIODS])

        for date in dates:
            report_batch = report_params.copy()
            report_batch[KEY_DATE] = date
            batches.append(report_batch)

        return batches


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
