# Xero Report Extractor
=============

## Description

This is a tool designed to extract data from Xero Accounting. It allows users to configure various parameters to tailor the extraction process according to their needs.

**Table of contents:**

[TOC]

## Functionality notes

This tool provides a dynamic UI form for configuration, enabling users to specify parameters such as date range, load type, and sync options. It supports both full load and incremental load modes, allowing users to choose between overwriting the destination table or upserting data into it. Additionally, it offers support for OAuth authentication and backfill mode, ensuring a seamless setup experience.

## Prerequisites

Xero User Account with access to source Xero instance.

## Supported endpoints

This Extractor is designed only to support Xero Reports API. Currently, only balance sheet report is supported.
If you require additional endpoints, please submit your request to [ideas.keboola.com](https://ideas.keboola.com/).

## Configuration

### Tenant IDs

- **Description**: Comma-separated list of Tenant IDs of tenants to download the data from. Leave empty to download all available. Data will be merged from all provided tenants.

### Report Parameters

- **Date**: Date must be set in YYYY-MM-DD format or to "last_month/last_year" which will use the last day of the previous month/year.
- **Timeframe**: The period size to compare to (MONTH, QUARTER, YEAR)
- **Tracking Option ID1 (Optional)**: The balance sheet will be filtered by this option if supplied. Note you cannot filter just by the TrackingCategory.
- **Tracking Option ID2 (Optional)**: If you want to filter by more than one tracking category option then you can specify a second option too. See the Balance Sheet report in Xero learn more about this behavior when filtering by tracking category options.
- **Standard Layout**: If you set this parameter to "true" then no custom report layouts will be applied to the response.
- **Payments Only**: Set this to true to get cash transactions only.

### Sync Options

- **Previous periods**: The number of previous periods to fetch data for. For example, if set to 3, the data for the current period and the previous 3 periods will be fetched. If set to 0, only the current period will be fetched.

### Destination

- **Load Type**: If Full load is used, the destination table will be overwritten every run. If incremental load is used, data will be upserted into the destination table. Tables with a primary key will have rows updated, tables without a primary key will have rows appended.

Development
-----------

If required, change local data folder (the `CUSTOM_FOLDER` placeholder) path to
your custom path in the `docker-compose.yml` file:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    volumes:
      - ./:/code
      - ./CUSTOM_FOLDER:/data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clone this repository, init the workspace and run the component with following
command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
git clone https://bitbucket.org/kds_consulting_team/kds-team.ex-xero-reports/src/main/ kds-team.ex-xero-reports
cd kds-team.ex-xero-reports
docker-compose build
docker-compose run --rm dev
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the test suite and lint check using this command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
docker-compose run --rm test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration
===========

For information about deployment and integration with KBC, please refer to the
[deployment section of developers
documentation](https://developers.keboola.com/extend/component/deployment/)
