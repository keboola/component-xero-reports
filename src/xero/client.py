import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List

from keboola.component.dao import OauthCredentials, TableDefinition

from xero_python.identity import IdentityApi
from xero_python.accounting import AccountingApi
from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.api_client.serializer import serialize

from xero_python.exceptions.http_status_exceptions import OAuth2InvalidGrantError, HTTPStatusException

# Always import utility to monkey patch BaseModel
from .utility import XeroException, EnhancedBaseModel


@dataclass
class Table:
    data: List[Dict]
    table_definition: TableDefinition


class XeroClient:
    def __init__(self, oauth_credentials: OauthCredentials) -> None:
        self._oauth_token_dict = oauth_credentials.data
        oauth2_token_obj = OAuth2Token(client_id=oauth_credentials.appKey,
                                       client_secret=oauth_credentials.appSecret)
        oauth2_token_obj.update_token(**self._oauth_token_dict)
        self._api_client = ApiClient(Configuration(oauth2_token=oauth2_token_obj),
                                     oauth2_token_getter=self.get_xero_oauth2_token_dict,
                                     oauth2_token_saver=self._set_xero_oauth2_token_dict)

        self._available_tenant_ids = None

    def get_xero_oauth2_token_dict(self) -> Dict:
        return self._oauth_token_dict

    def _set_xero_oauth2_token_dict(self, new_token: Dict) -> None:
        self._oauth_token_dict = new_token

    def refresh_available_tenant_ids(self) -> None:
        identity_api = IdentityApi(self._api_client)
        available_tenants = []
        try:
            for connection in identity_api.get_connections():
                tenant = serialize(connection)
                available_tenants.append(tenant.get("tenantId"))
        except (OAuth2InvalidGrantError, HTTPStatusException) as oauth_err:
            raise XeroException(oauth_err) from oauth_err
        self._available_tenant_ids = available_tenants

    def force_refresh_token(self):
        try:
            self._api_client.refresh_oauth2_token()
        except HTTPStatusException as http_error:
            raise XeroException(
                "Failed to authenticate the client, please reauthorize the component") from http_error

    def get_available_tenant_ids(self):
        if not self._available_tenant_ids:
            self.refresh_available_tenant_ids()
        return self._available_tenant_ids

    def get_balance_sheet_report(self, tenant_id: str, **kwargs) -> Iterable[List[EnhancedBaseModel]]:
        if kwargs:
            logging.info(f"Getting balance sheet report with parameters: {kwargs}")
        accounting_api = AccountingApi(self._api_client)
        return accounting_api.get_report_balance_sheet(tenant_id, **kwargs).to_list()
