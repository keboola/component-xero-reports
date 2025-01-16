# Xero Reports Extractor
=============

## Description

This tool is designed to extract data from Xero Accounting. It allows users to configure various parameters to tailor the extraction process according to their needs.

**Table of Contents:**

[TOC]

## Functionality Notes

This tool provides a dynamic UI form for configuration, enabling users to specify parameters such as the date range, load type, and sync options. It supports both full load and incremental load modes, allowing users to choose between overwriting the destination table or upserting data into it. Additionally, it offers support for OAuth authentication and backfill mode, ensuring a seamless setup experience.

## Prerequisites

A Xero user account with access to the source Xero instance is required.

## Supported Endpoints

This extractor is designed only to support the Xero Reports API. Currently, only the balance sheet report is supported.
If you require additional endpoints, please submit your request to [ideas.keboola.com](https://ideas.keboola.com/).

## Configuration

### Tenant IDs

- **Description**: A comma-separated list of Tenant IDs to download data from. Leave empty to download from all available tenants. Data will be merged from all provided tenants.

### Report Parameters

- **Date**: The date must be set in the YYYY-MM-DD format or as "last_month/last_year," which will use the last day of the previous month/year.
- **Timeframe**: The period size to compare (MONTH, QUARTER, YEAR).
- **Tracking Option ID1 (Optional)**: The balance sheet will be filtered by this option if supplied. Note that you cannot filter by the tracking category alone.
- **Tracking Option ID2 (Optional)**: If you want to filter by more than one tracking category option, you can specify a second option here. See the Xero Balance Sheet report to learn more about filtering behavior when using tracking category options.
- **Standard Layout**: If this parameter is set to "true," no custom report layouts will be applied to the response.
- **Payments Only**: Set this to "true" to retrieve only cash transactions.

### Sync Options

- **Previous periods**: The number of previous periods to fetch data for. For example, if set to 3, data for the current period and the previous 3 periods will be fetched. If set to 0, only the current period will be fetched.

### Destination

- **Load Type**: If "Full Load" is used, the destination table will be overwritten with every run. If "Incremental Load" is used, data will be upserted into the destination table. Tables with a primary key will have rows updated, while tables without a primary key will have rows appended.

Development
-----------

If required, change the local data folder (the `CUSTOM_FOLDER` placeholder) path to
your custom path in the `docker-compose.yml` file:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    volumes:
      - ./:/code
      - ./CUSTOM_FOLDER:/data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clone this repository, initialize the workspace, and run the component with the following
commands:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
git clone https://bitbucket.org/kds_consulting_team/kds-team.ex-xero-reports/src/main/ kds-team.ex-xero-reports
cd kds-team.ex-xero-reports
docker-compose build
docker-compose run --rm dev
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the test suite and lint checks using this command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
docker-compose run --rm test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration
===========

For information about deployment and integration with Keboola, please refer to the
[deployment section of the developer
documentation](https://developers.keboola.com/extend/component/deployment/).
