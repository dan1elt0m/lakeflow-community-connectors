# Lakeflow Microsoft Purview Community Connector

This documentation describes how to configure and use the **Microsoft Purview** Lakeflow community connector to ingest governance metadata from the Microsoft Purview Unified Catalog and Data Map APIs into Databricks.


## Prerequisites

- **Microsoft Purview account**: A Purview account with the Unified Catalog and Data Map enabled.
- **Authentication credentials** (one of the following):
  - **DefaultAzureCredential** (recommended for Databricks on Azure): Works automatically with `az login`, environment variables, or managed identity. No extra configuration needed.
  - **Service principal (client secret)**: An Azure AD app registration with `tenant_id`, `client_id`, and `client_secret`.
- **Purview role assignments**:
  - **Unified Catalog** (for `domains` and `data_products`): The identity must have the **Data Catalog Reader** role assigned within the Purview Unified Catalog (Catalog Management > Governance domains > Roles).
  - **Data Map** (for `data_assets`): The identity must have the **Data Curator** role assigned at the root collection level (Data Map > Collections > root collection > Role Assignments).
- **Network access**: The environment running the connector must be able to reach:
  - `https://api.purview-service.microsoft.com` (Unified Catalog API)
  - `https://{account_name}.purview.azure.com` (Data Map API)
  - `https://login.microsoftonline.com` (Azure AD token endpoint, for client_secret auth)
- **Lakeflow / Databricks environment**: A workspace where you can register a Lakeflow community connector and run ingestion pipelines.

## Setup

### Required Connection Parameters

Provide the following **connection-level** options when configuring the connector.

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `purview_account_name` | string | Yes | The Purview account name. Used to construct the Data Map API base URL (`https://{name}.purview.azure.com`). | `mycompany` |
| `auth_method` | string | No | Authentication method. `"default_credential"` uses Azure DefaultAzureCredential (az cli, env vars, managed identity). `"client_secret"` uses explicit OAuth2 client credentials. Defaults to `"default_credential"`. | `client_secret` |
| `tenant_id` | string | No | Azure AD tenant ID (GUID). Required when `auth_method` is `"client_secret"`. | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `client_id` | string | No | Application (client) ID (GUID). Required when `auth_method` is `"client_secret"`. | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `client_secret` | string | No | Client secret value. Required when `auth_method` is `"client_secret"`. | `your-secret-value` |

This connector does not require any table-specific options passed through `externalOptionsAllowList`. You do not need to include `externalOptionsAllowList` as a connection parameter.

### Obtaining the Required Parameters

- **Purview account name**:
  1. Sign in to the [Azure Portal](https://portal.azure.com).
  2. Navigate to your Microsoft Purview account resource.
  3. The account name is shown in the resource overview. It is the subdomain of your Data Map endpoint (e.g., if the endpoint is `https://mycompany.purview.azure.com`, the account name is `mycompany`).

- **Service principal credentials** (only needed for `client_secret` auth):
  1. In Azure Portal, navigate to **Azure Active Directory > App registrations**.
  2. Create a new registration or select an existing one.
  3. Copy the **Application (client) ID** and **Directory (tenant) ID** from the overview page.
  4. Under **Certificates & secrets**, create a new client secret and copy the secret value.
  5. Assign the required Purview roles to this service principal (see Prerequisites).

- **DefaultAzureCredential** (default, no extra setup on Databricks):
  - On Azure Databricks with a system-assigned managed identity, authentication works automatically.
  - For local development, run `az login` first.
  - Ensure the identity has the required Purview role assignments.

### Create a Unity Catalog Connection

A Unity Catalog connection for this connector can be created in two ways via the UI:

1. Follow the **Lakeflow Community Connector** UI flow from the **Add Data** page.
2. Select any existing Lakeflow Community Connector connection for this source or create a new one.
3. Provide `purview_account_name` and, if using client secret auth, the `auth_method`, `tenant_id`, `client_id`, and `client_secret` parameters.

The connection can also be created using the standard Unity Catalog API.


## Supported Objects

The Purview connector exposes a **static list** of three tables:

- `domains`
- `data_products`
- `data_assets`

### Object summary, primary keys, and ingestion mode

| Table | Description | API Surface | Ingestion Type | Primary Key | Incremental Cursor |
|-------|-------------|-------------|----------------|-------------|-------------------|
| `domains` | Business domains from the Unified Catalog | Unified Catalog API | `snapshot` | `id` | n/a |
| `data_products` | Data products from the Unified Catalog | Unified Catalog API | `snapshot` | `id` | n/a |
| `data_assets` | Data assets discovered via the Data Map search API | Data Map API | `cdc` | `id` | `updateTime` |

### Ingestion details

- **`domains`** and **`data_products`**: Full snapshot on every run. The connector reads all records from the Unified Catalog API and replaces the previous snapshot.
- **`data_assets`**: Supports incremental (CDC) ingestion using `updateTime` (Unix timestamp in milliseconds) as the cursor. The connector uses a sliding time-window approach with a configurable window size (default: 1 day). A 1-hour lookback is applied automatically to catch late-arriving updates. The `data_assets` table also supports partitioned streaming for parallel reads across time ranges.

### Schema highlights

- **`domains`**: Includes nested `systemData` (creation/modification timestamps and users), `domains` array (platform domain associations with related collections), and `managedAttributes` array.
- **`data_products`**: Includes nested `contacts` (owner, expert, databaseAdmin), `termsOfUse` and `documentation` link arrays, `managedAttributes`, `additionalProperties` (asset count), and `systemData`.
- **`data_assets`**: Flat structure with `classification`, `label`, and `assetType` as string arrays; `term` as an array of glossary term objects; and `contact` as an array of contact objects.

Full schemas are defined in the connector implementation and align with the Microsoft Purview API documentation.


## Table Configurations

### Source & Destination

These are set directly under each `table` object in the pipeline spec:

| Option | Required | Description |
|---|---|---|
| `source_table` | Yes | Table name in the source system |
| `destination_catalog` | No | Target catalog (defaults to pipeline's default) |
| `destination_schema` | No | Target schema (defaults to pipeline's default) |
| `destination_table` | No | Target table name (defaults to `source_table`) |

### Common `table_configuration` options

These are set inside the `table_configuration` map alongside any source-specific options:

| Option | Required | Description |
|---|---|---|
| `scd_type` | No | `SCD_TYPE_1` (default) or `SCD_TYPE_2`. Only applicable to tables with CDC or SNAPSHOT ingestion mode. |
| `primary_keys` | No | List of columns to override the connector's default primary keys |
| `sequence_by` | No | Column used to order records for SCD Type 2 change tracking |

### Source-specific `table_configuration` options

The `domains` and `data_products` tables do not require any additional table-level options.

The `data_assets` table supports the following optional configuration options:

| Option | Required | Default | Description |
|---|---|---|---|
| `window_seconds` | No | `86400` (1 day) | Size of the sliding time-window in seconds for incremental reads. Controls how large each partition is in streaming mode. |
| `page_size` | No | `1000` | Number of records to request per API page. |
| `max_records_per_batch` | No | `10000` (partitioned) / `1000` (simple) | Maximum number of records returned per batch or partition. |
| `start_timestamp` | No | `0` (epoch) | Initial cursor value in Unix milliseconds. Used only on the first run when no stored offset exists and the simple stream reader is used. |


## Data Type Mapping

Purview API fields are mapped to Spark types as follows:

| Purview JSON Type | Example Fields | Spark Type | Notes |
|-------------------|----------------|------------|-------|
| string | `id`, `name`, `description`, `qualifiedName` | `StringType` | UUIDs and plain text are stored as strings. |
| string (enum) | `status`, `type`, `entityType` | `StringType` | Enum values are stored as plain strings. |
| string (datetime) | `systemData.createdAt`, `systemData.lastModifiedAt` | `TimestampType` | ISO 8601 timestamps are parsed to Spark timestamps. High-precision values (>6 fractional digits) are truncated to microseconds. |
| boolean | `isRestricted`, `endorsed` | `BooleanType` | Standard `true`/`false` values. |
| integer (int64) | `createTime`, `updateTime`, `activeSubscriberCount` | `LongType` | Unix timestamps in milliseconds and counts. |
| number (double) | `dataQualityScore` | `DoubleType` | Floating-point scores. |
| object | `systemData`, `contacts`, `thumbnail` | `StructType` | Nested objects are preserved as Spark structs. |
| array of string | `audience`, `classification`, `label`, `assetType` | `ArrayType(StringType)` | Arrays of primitive values. |
| array of object | `domains`, `managedAttributes`, `term`, `contact` | `ArrayType(StructType)` | Arrays of nested structures are preserved. |
| nullable fields | `description`, `parentId`, `owner` | Same as base type + `null` | Missing fields are surfaced as `null`. |


## How to Run

### Step 1: Clone/Copy the Source Connector Code

Use the Lakeflow Community Connector UI to copy or reference the Purview connector source in your workspace. This will typically place the connector code under a project path that Lakeflow can load.

### Step 2: Configure Your Pipeline

In your pipeline code, configure a `pipeline_spec` that references a Unity Catalog connection using this Purview connector and the tables to ingest.

Example `pipeline_spec` to ingest all three tables:

```json
{
  "pipeline_spec": {
    "connection_name": "purview_connection",
    "object": [
      {
        "table": {
          "source_table": "domains"
        }
      },
      {
        "table": {
          "source_table": "data_products"
        }
      },
      {
        "table": {
          "source_table": "data_assets"
        }
      }
    ]
  }
}
```

- `connection_name` must point to the UC connection configured with your Purview credentials.
- For each `table`, `source_table` must be one of: `domains`, `data_products`, or `data_assets`.
- The `domains` and `data_products` tables require no additional options.
- The `data_assets` table works out of the box but can be tuned with `window_seconds`, `page_size`, or `max_records_per_batch` if needed.

### Step 3: Run and Schedule the Pipeline

Run the pipeline using your standard Lakeflow / Databricks orchestration (e.g., a scheduled job or workflow).

- **`domains` and `data_products`**: These are snapshot tables. Every run fetches the full current state. Schedule frequency depends on how often your governance metadata changes (daily is usually sufficient).
- **`data_assets`**: This is an incremental (CDC) table. On the first run, it backfills all assets. On subsequent runs, it picks up changes since the last cursor using `updateTime`-based filtering with an automatic 1-hour lookback for late updates.

#### Best Practices

- **Start small**: Begin by syncing a single table (e.g., `domains`) to validate your connection and permissions before adding all three.
- **Use incremental sync for data_assets**: The CDC pattern with `updateTime` minimizes API calls on subsequent runs.
- **Tune window size for large catalogs**: If your Purview instance has many assets, consider adjusting `window_seconds` to control partition sizes and parallelism.
- **Monitor rate limits**: Purview APIs enforce rate limits. The connector includes built-in exponential backoff retry (up to 5 retries) for HTTP 429, 500, and 503 responses, with Retry-After header support.

#### Troubleshooting

Common issues and how to address them:

- **Authentication failures (`401` / `403`)**:
  - For `default_credential`: Verify the managed identity or `az login` session is active and has the required Purview roles.
  - For `client_secret`: Verify that `tenant_id`, `client_id`, and `client_secret` are correct and not expired.
  - Ensure the identity has **Data Catalog Reader** (for domains/data_products) and **Data Curator** (for data_assets) roles assigned.
- **Empty results for `domains` or `data_products`**:
  - Confirm that business domains and data products have been created in the Purview Unified Catalog.
  - Check that the identity has visibility into the domains (role assignments may be scoped per domain).
- **Empty results for `data_assets`**:
  - Verify the `purview_account_name` is correct and points to the right Purview instance.
  - Confirm the Data Map has registered and scanned data sources.
  - Check that the identity has `Data Curator` at the root collection level.
- **Rate limiting (`429` responses)**:
  - The connector retries automatically with exponential backoff. If rate limiting persists, widen your schedule interval or reduce `page_size`.
- **Timestamp precision errors**:
  - The connector automatically truncates Purview timestamps from 7 fractional digits to 6 (microseconds) for Spark compatibility. No action is needed.


## References

- Connector implementation: `src/databricks/labs/community_connector/sources/purview/purview.py`
- Connector schemas: `src/databricks/labs/community_connector/sources/purview/purview_schemas.py`
- Connector API documentation: `src/databricks/labs/community_connector/sources/purview/purview_api_doc.md`
- Microsoft Purview documentation:
  - [Microsoft Purview Unified Catalog REST API](https://learn.microsoft.com/en-us/rest/api/purview/datagovernance/)
  - [Microsoft Purview Data Map REST API](https://learn.microsoft.com/en-us/rest/api/purview/datamapdataplane/)
  - [DefaultAzureCredential (azure-identity)](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential)
