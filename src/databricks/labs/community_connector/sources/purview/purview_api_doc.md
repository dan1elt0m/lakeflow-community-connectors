# Microsoft Purview API Documentation

## Overview

Microsoft Purview is a unified data governance solution that covers two distinct API surfaces:

1. **Unified Catalog API** (`api-version: 2025-09-15-preview`) — The newer, purpose-built governance API covering business domains, data products, glossary terms, OKRs, and policies. This is the preferred API for governance objects.
2. **Data Map API** (`api-version: 2023-09-01`) — The Apache Atlas-compatible API for data asset discovery, entity management, and cataloging. This is the API for querying registered data assets.

The connector targets three tables:
- `domains` — via Unified Catalog API (Business Domain operations)
- `data_products` — via Unified Catalog API (Data Products operations)
- `data_assets` — via Data Map API (Discovery/Query + Entity/Get operations)

**Base URL (Unified Catalog):** `https://api.purview-service.microsoft.com/`
**Base URL (Data Map / new portal):** `https://api.purview-service.microsoft.com/`
**Base URL (Data Map / classic portal):** `https://{accountName}.purview.azure.com/`

All three tables use the same authentication mechanism.

---

## Authorization

### Preferred Method: Azure AD OAuth2 Client Credentials (Service Principal)

The connector uses the **client credentials flow** (no user-facing OAuth). It stores `tenant_id`, `client_id`, and `client_secret` and exchanges them for a Bearer token at runtime.

**Token endpoint:**
```
POST https://login.microsoftonline.com/{tenant_id}/oauth2/token
```

**Request body (form-encoded):**

| Parameter | Value |
|-----------|-------|
| `client_id` | Application (client) ID from Azure Entra ID |
| `client_secret` | Client secret value |
| `grant_type` | `client_credentials` |
| `resource` | `https://purview.azure.net` |

**Example request (Python):**
```python
import requests

token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
payload = {
    "client_id": client_id,
    "client_secret": client_secret,
    "grant_type": "client_credentials",
    "resource": "https://purview.azure.net",
}
response = requests.post(token_url, data=payload)
access_token = response.json()["access_token"]
```

**Example token response:**
```json
{
    "token_type": "Bearer",
    "expires_in": "86399",
    "ext_expires_in": "86399",
    "expires_on": "1621038348",
    "not_before": "1620951648",
    "resource": "https://purview.azure.net",
    "access_token": "<<access_token>>"
}
```

Tokens expire after ~24 hours (`expires_in: 86399` seconds). The connector must refresh the token before expiry.

**Using the token — all API calls include:**
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

### Required Permissions (Unified Catalog — domains and data_products)

The service principal must be assigned the **Data Catalog Reader** role within the Purview Unified Catalog:
1. Navigate to Microsoft Purview portal > Unified Catalog > Catalog Management > Governance domains.
2. Select the domain > Roles tab.
3. Assign `Data Catalog Reader` to the service principal.

This role grants read access to: OKRs, Business Domains, Critical Data Elements, Data Products, Terms.

### Required Permissions (Data Map — data_assets)

The service principal must be assigned the **Data Curator** role at the root collection level:
1. Navigate to Microsoft Purview portal > Data Map > Collections > root collection.
2. Select Role Assignments tab.
3. Assign `Data Curator` to the service principal.

### Alternative Auth Method

The OAuth2 implicit flow (interactive browser) is listed in the API security definition but is **not suitable** for connector use. Stick to the client credentials flow documented above.

---

## Object List

The connector supports three static objects. All are accessible via API.

| Table Name | API Surface | Endpoint Pattern |
|------------|-------------|------------------|
| `domains` | Unified Catalog API | `GET {endpoint}/datagovernance/catalog/businessdomains` |
| `data_products` | Unified Catalog API | `GET {endpoint}/datagovernance/catalog/dataProducts` |
| `data_assets` | Data Map API | `POST {endpoint}/datamap/api/search/query` |

Object list is **static** — these three objects are predefined, not discovered at runtime.

---

## Object Schema

### Table: `domains`

Retrieved from the Business Domain Enumerate and Get operations of the Unified Catalog API.

**Enumerate endpoint:**
```
GET {endpoint}/datagovernance/catalog/businessdomains?api-version=2025-09-15-preview
```

**Get single domain endpoint:**
```
GET {endpoint}/datagovernance/catalog/businessdomains/{domainId}?api-version=2025-09-15-preview
```

**Full schema (Domain object):**

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | string (uuid) | No | Primary key. Unique identifier of the domain. |
| `name` | string | No | The name of the domain. |
| `description` | string | Yes | The description of the domain. |
| `parentId` | string (uuid) | Yes | Identifier of the parent domain (for hierarchical domains). |
| `status` | string (enum) | No | Lifecycle state: `DRAFT`, `PUBLISHED`, `EXPIRED`. |
| `type` | string (enum) | No | Domain type: `FunctionalUnit`, `LineOfBusiness`, `DataDomain`, `Regulatory`, `Project`. |
| `isRestricted` | boolean | Yes | Whether the domain is restricted. |
| `thumbnail.color` | string | Yes | Hex color code for the domain thumbnail (e.g., `#FFFFFF`). |
| `domains` | array | Yes | List of platform domains (nested collection associations). |
| `domains[].name` | string | Yes | Internal name of the platform domain. |
| `domains[].friendlyName` | string | Yes | Display name of the platform domain. |
| `domains[].relatedCollections` | array | Yes | Collections associated with this platform domain. |
| `domains[].relatedCollections[].name` | string | Yes | Internal name of the related collection. |
| `domains[].relatedCollections[].friendlyName` | string | Yes | Display name of the related collection. |
| `domains[].relatedCollections[].parentCollection.refName` | string | Yes | Reference name of the parent collection. |
| `domains[].relatedCollections[].parentCollection.type` | string | Yes | Parent collection type: `CollectionReference`. |
| `managedAttributes` | array | Yes | Custom managed attributes configured for the domain. |
| `managedAttributes[].name` | string | Yes | Name of the managed attribute. |
| `managedAttributes[].value` | string | Yes | Value of the managed attribute. |
| `managedAttributes[].isRequired` | boolean | Yes | Whether the attribute is required. |
| `systemData.createdAt` | string (datetime) | Yes | ISO 8601 timestamp when the domain was created. |
| `systemData.createdBy` | string (uuid) | Yes | User ID who created the domain. |
| `systemData.lastModifiedAt` | string (datetime) | Yes | ISO 8601 timestamp of last modification. Used as cursor for incremental sync. |
| `systemData.lastModifiedBy` | string (uuid) | Yes | User ID who last modified the domain. |
| `systemData.expiredAt` | string (datetime) | Yes | ISO 8601 timestamp when the domain expired (if applicable). |
| `systemData.expiredBy` | string (uuid) | Yes | User ID who expired the domain. |

**Sample response (single domain):**
```json
{
  "id": "4e74f902-62f5-49f4-8258-92ed2b8537ba",
  "name": "myBusinessDomain",
  "description": "This is my domain",
  "parentId": "8e74f902-62f5-49f4-8258-92ed2b8537ba",
  "status": "PUBLISHED",
  "type": "FunctionalUnit",
  "isRestricted": false,
  "thumbnail": { "color": "#FFFFFF" },
  "domains": [
    {
      "name": "myBusinessDomain",
      "friendlyName": "My Business Domain",
      "relatedCollections": [
        {
          "name": "relatedCollection",
          "friendlyName": "My Business Domain",
          "parentCollection": { "refName": "reference1", "type": "CollectionReference" }
        }
      ]
    }
  ],
  "managedAttributes": [{ "name": "costCenter", "value": "eng-123", "isRequired": false }],
  "systemData": {
    "lastModifiedAt": "2025-01-15T10:00:00.000Z",
    "lastModifiedBy": "766BF2B9-5D8A-4FB1-B8D5-D30A53E22A9E",
    "createdAt": "2024-06-01T08:00:00.000Z",
    "createdBy": "766BF2B9-5D8A-4FB1-B8D5-D30A53E22A9E",
    "expiredAt": null,
    "expiredBy": null
  }
}
```

---

### Table: `data_products`

Retrieved from the Data Products List and Get operations of the Unified Catalog API.

**List endpoint:**
```
GET {endpoint}/datagovernance/catalog/dataProducts?api-version=2025-09-15-preview
```

**Get single data product endpoint:**
```
GET {endpoint}/datagovernance/catalog/dataProducts/{dataProductId}?api-version=2025-09-15-preview
```

**Full schema (DataProduct object):**

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | string (uuid) | No | Primary key. Unique identifier of the data product. |
| `name` | string | No | The name of the data product. |
| `domain` | string (uuid) | No | The business domain ID this data product belongs to. Foreign key to `domains.id`. |
| `type` | string (enum) | No | Data product type. Values: `Master`, `Reference`, `Analytical`, `AI`, `MasterDataAndReferenceData`, `BusinessSystemOrApplication`, `ModelTypes`, `DashboardsOrReports`, `Operational`, `MLAITrainingDataSet`, `MLAITestingDataSet`, `TransactionalDataset`, `AnalyticsModel`, `SemanticModel`. |
| `description` | string | Yes | Description of the data product. |
| `businessUse` | string | Yes | The business use case or purpose of the data product. |
| `status` | string (enum) | No | Lifecycle state: `DRAFT`, `PUBLISHED`, `EXPIRED`. |
| `endorsed` | boolean | No | Whether the data product has been endorsed/certified. |
| `updateFrequency` | string (enum) | Yes | How often the data product is refreshed: `Hourly`, `Daily`, `Weekly`, `Monthly`, `Quarterly`, `Yearly`. |
| `sensitivityLabel` | string | Yes | The sensitivity label identifier applied to this data product. |
| `dataQualityScore` | number (double) | Yes | Computed data quality score. |
| `activeSubscriberCount` | integer | Yes | Number of active subscribers to this data product. |
| `audience` | array of string (enum) | Yes | Target audience. Values: `DataEngineer`, `BIEngineer`, `DataAnalyst`, `DataScientist`, `BusinessAnalyst`, `SoftwareEngineer`, `BusinessUser`, `Executive`. |
| `contacts` | object | Yes | Contacts associated with the data product. |
| `contacts.owner` | array | Yes | List of owners. Each has `id` (uuid) and `description` (string). |
| `contacts.expert` | array | Yes | List of experts. Each has `id` (uuid) and `description` (string). |
| `contacts.databaseAdmin` | array | Yes | List of database admins. Each has `id` (uuid) and `description` (string). |
| `termsOfUse` | array | Yes | Terms of use links. |
| `termsOfUse[].url` | string (uri) | Yes | URL of the terms of use document. |
| `termsOfUse[].name` | string | Yes | Display name of the terms of use link. |
| `termsOfUse[].dataAssetId` | string (uuid) | Yes | Associated data asset ID. |
| `documentation` | array | Yes | Documentation links. |
| `documentation[].url` | string (uri) | Yes | URL of the documentation. |
| `documentation[].name` | string | Yes | Display name of the documentation link. |
| `documentation[].dataAssetId` | string (uuid) | Yes | Associated data asset ID. |
| `managedAttributes` | array | Yes | Custom managed attributes for the data product. |
| `managedAttributes[].name` | string | Yes | Attribute name. |
| `managedAttributes[].value` | string | Yes | Attribute value. |
| `managedAttributes[].isRequired` | boolean | Yes | Whether the attribute is required. |
| `additionalProperties.assetCount` | integer (int64) | Yes | Number of data assets associated with the data product. |
| `systemData.createdAt` | string (datetime) | Yes | ISO 8601 timestamp when the data product was created. |
| `systemData.createdBy` | string (uuid) | Yes | User ID who created the data product. |
| `systemData.lastModifiedAt` | string (datetime) | Yes | ISO 8601 timestamp of last modification. Used as cursor for incremental sync. |
| `systemData.lastModifiedBy` | string (uuid) | Yes | User ID who last modified the data product. |
| `systemData.expiredAt` | string (datetime) | Yes | ISO 8601 timestamp when the data product expired. |
| `systemData.expiredBy` | string (uuid) | Yes | User ID who expired the data product. |

**Sample response (list):**
```json
{
  "value": [
    {
      "id": "4e74f902-62f5-49f4-8258-92ed2b8537ba",
      "name": "Superstore Sales",
      "domain": "7e74f902-62f5-49f4-8258-92ed2b8537ba",
      "type": "Analytical",
      "description": "Sales data and performance metrics for the superstore.",
      "businessUse": "Forecasting of future revenue. Sales trend analysis.",
      "status": "PUBLISHED",
      "endorsed": true,
      "updateFrequency": "Daily",
      "sensitivityLabel": "9620744d-630c-4d07-b8db-541ec20e1a2a",
      "dataQualityScore": 0.92,
      "activeSubscriberCount": 14,
      "audience": ["DataAnalyst", "BusinessAnalyst"],
      "contacts": {
        "owner": [{ "id": "4e74f902-62f5-49f4-8258-92ed2b8537ba", "description": "Product owner" }],
        "expert": [{ "id": "5e74f902-62f5-49f4-8258-92ed2b8537ba", "description": "Domain expert" }],
        "databaseAdmin": []
      },
      "termsOfUse": [{ "url": "https://internal.example.com/tos", "name": "Internal ToS", "dataAssetId": null }],
      "documentation": [{ "url": "https://wiki.example.com/sales", "name": "Sales Wiki", "dataAssetId": null }],
      "managedAttributes": [],
      "additionalProperties": { "assetCount": 12 },
      "systemData": {
        "createdAt": "2024-06-01T08:00:00.000Z",
        "createdBy": "766BF2B9-5D8A-4FB1-B8D5-D30A53E22A9E",
        "lastModifiedAt": "2025-03-01T12:00:00.000Z",
        "lastModifiedBy": "766BF2B9-5D8A-4FB1-B8D5-D30A53E22A9E",
        "expiredAt": null,
        "expiredBy": null
      }
    }
  ]
}
```

---

### Table: `data_assets`

Retrieved from the Data Map Discovery/Query API (search) and optionally enriched with Entity/Get for full detail.

**Search/list endpoint (POST):**
```
POST {endpoint}/datamap/api/search/query?api-version=2023-09-01
```

**Get single entity endpoint (GET):**
```
GET {endpoint}/datamap/api/atlas/v2/entity/guid/{guid}?api-version=2023-09-01
```

**Search response fields (QueryResultValue):**

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | string (uuid) | No | Primary key. GUID of the entity/asset. |
| `qualifiedName` | string | No | Fully qualified unique name (e.g., `https://account.blob.core.windows.net/path/file.csv`). |
| `name` | string | No | Display name of the asset. |
| `description` | string | Yes | Description of the asset. |
| `owner` | string | Yes | Owner of the asset. |
| `entityType` | string | No | Atlas entity type (e.g., `azure_blob_path`, `azure_sql_mi_table`, `snowflake_table`). |
| `assetType` | array of string | No | Human-readable asset type category (e.g., `["Azure Blob Storage"]`, `["Azure SQL Managed Instance"]`). |
| `classification` | array of string | Yes | Classifications applied (e.g., sensitive data labels). |
| `label` | array of string | Yes | Labels applied to the asset. |
| `term` | array of object | Yes | Glossary terms assigned. Each has `name`, `glossaryName`, `guid`. |
| `contact` | array of object | Yes | Contacts. Each has `id`, `info`, `contactType` (`Expert` or `Owner`). |
| `@search.score` | number | No | Search relevance score (not persisted). |
| `@search.highlights` | object | Yes | Highlighted text fragments (not persisted). |

**Full entity fields (AtlasEntity — from Entity/Get):**

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `guid` | string | No | Primary key. Same as `id` in search results. |
| `typeName` | string | No | Atlas entity type name. |
| `status` | string (enum) | No | `ACTIVE` or `DELETED`. |
| `createdBy` | string | Yes | User who created the entity. |
| `updatedBy` | string | Yes | User who last updated the entity. |
| `createTime` | integer (int64) | Yes | Unix timestamp (ms) when entity was created. |
| `updateTime` | integer (int64) | Yes | Unix timestamp (ms) when entity was last updated. Used as cursor for incremental sync. |
| `version` | integer (int64) | No | Entity version number. |
| `collectionId` | string | Yes | Collection ID the entity belongs to. |
| `homeId` | string | Yes | Home ID of the entity. |
| `isIncomplete` | boolean | Yes | Whether this is a shell/placeholder entity. |
| `proxy` | boolean | Yes | Whether a proxy exists for this entity. |
| `provenanceType` | integer | Yes | Provenance type code. |
| `lastModifiedTS` | string | Yes | ETag for concurrency control. |
| `attributes` | object | Yes | Dynamic entity attributes (vary by `typeName`). Common attributes: `qualifiedName`, `name`, `description`, `owner`, `modifiedTime`, `createTime`, `type`. |
| `attributes.qualifiedName` | string | No | Fully qualified name (always present in attributes). |
| `attributes.name` | string | No | Asset name. |
| `attributes.description` | string | Yes | Asset description. |
| `attributes.owner` | string | Yes | Owner string. |
| `attributes.modifiedTime` | integer | Yes | Unix timestamp (ms) of last modification. |
| `attributes.createTime` | integer | Yes | Unix timestamp (ms) of creation. |
| `attributes.type` | string | Yes | Asset-type-specific type field (e.g., `TABLE`, `VIEW`). |
| `businessAttributes` | object | Yes | Business metadata attributes. |
| `classifications` | array | Yes | Classifications applied to the entity. |
| `classifications[].typeName` | string | Yes | Classification type name. |
| `classifications[].entityGuid` | string | Yes | GUID of the classified entity. |
| `classifications[].entityStatus` | string | Yes | `ACTIVE` or `DELETED`. |
| `classifications[].validityPeriods` | array | Yes | Time boundaries for this classification. |
| `classifications[].removePropagationsOnEntityDelete` | boolean | Yes | Whether to remove propagation on entity delete. |
| `classifications[].lastModifiedTS` | string | Yes | ETag. |
| `contacts` | object | Yes | Contacts dictionary. Keys are `Expert` and `Owner`. |
| `contacts.Expert` | array | Yes | Each has `id` (uuid) and `info` (string). |
| `contacts.Owner` | array | Yes | Each has `id` (uuid) and `info` (string). |
| `customAttributes` | object | Yes | Custom attributes dictionary. |
| `labels` | array of string | Yes | Labels applied to the entity. |
| `meanings` | array | Yes | Glossary term assignments. |
| `meanings[].termGuid` | string (uuid) | Yes | GUID of the assigned term. |
| `meanings[].relationGuid` | string (uuid) | Yes | GUID of the assignment relationship. |
| `meanings[].displayText` | string | Yes | Display text of the term. |
| `meanings[].status` | string (enum) | Yes | Assignment status: `DISCOVERED`, `PROPOSED`, `IMPORTED`, `VALIDATED`, `DEPRECATED`, `OBSOLETE`, `OTHER`. |
| `meanings[].confidence` | integer | Yes | Confidence score of the assignment. |
| `meanings[].createdBy` | string | Yes | User who created the assignment. |
| `meanings[].description` | string | Yes | Description of the assignment. |
| `meanings[].expression` | string | Yes | Expression used in the assignment. |
| `meanings[].steward` | string | Yes | Steward of the term. |
| `relationshipAttributes` | object | Yes | Relationship attributes (e.g., `schema`, `meanings`, `inputToProcesses`, `outputFromProcesses`). |

---

## Get Object Primary Keys

### `domains` table

Primary key: **`id`** (string, UUID)
- Stable, server-assigned on creation.
- Present in all enumerate and get responses.

### `data_products` table

Primary key: **`id`** (string, UUID)
- Stable, server-assigned on creation.
- Present in all list and get responses.

### `data_assets` table

Primary key: **`id`** (string, UUID) — from search results, same as `guid` in the entity detail response.
- Stable, server-assigned Atlas GUID.
- The field is named `id` in search query responses and `guid` in the entity get response.

---

## Object Ingestion Type

| Table | Ingestion Type | Rationale |
|-------|---------------|-----------|
| `domains` | `snapshot` | The Business Domain Enumerate API does not expose a filter by `lastModifiedAt`. No ordering or filter by modification time is available in the enumerate endpoint. Full snapshot is required on each sync. |
| `data_products` | `snapshot` | The Data Products List API supports `orderBy` but does not expose a filter by `lastModifiedAt`. No server-side filtering by modification time is documented. Full snapshot required. |
| `data_assets` | `cdc` | The Data Map Discovery Query API supports filtering by `modifiedTime` with `ge` operator and time range strings (`LAST_24H`, `LAST_7D`, `LAST_30D`, `LAST_365D`). Deleted entities are returned with `status: DELETED` in the entity get response and can be detected. This enables incremental reads with upserts. |

**Note on `data_assets` incremental read:** The Discovery Query API does not support ordering by `updateTime` in a way that produces a stable cursor. Instead, use a time-range filter on `modifiedTime` with the `ge` operator using the last-synced Unix epoch timestamp to fetch assets modified since the last run. Include a lookback window (e.g., subtract 1 hour) to handle clock skew.

---

## Read API for Data Retrieval

### Table: `domains`

**Method:** GET
**URL:** `{endpoint}/datagovernance/catalog/businessdomains?api-version=2025-09-15-preview`

**Query parameters:**

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `api-version` | Yes | string | Must be `2025-09-15-preview` |
| `$skipToken` | No | string | Continuation token for next page. Use the `nextLink` URL from the prior response. |
| `writeOnly` | No | boolean | If `true`, only returns domains where the caller has write permission. Use `false` or omit for read-only connector. |

**Pagination:** The response contains a `nextLink` field (full URL including skip token). Follow `nextLink` until it is absent or null. There is no explicit page size control — the API controls page size internally.

**Example first-page request:**
```http
GET https://api.purview-service.microsoft.com/datagovernance/catalog/businessdomains?api-version=2025-09-15-preview
Authorization: Bearer {access_token}
```

**Example next-page request:**
```http
GET https://api.purview-service.microsoft.com/datagovernance/catalog/businessdomains?api-version=2025-09-15-preview&$skipToken=pkpqdwxhycymmwg
Authorization: Bearer {access_token}
```

**Response envelope:**
```json
{
  "value": [ /* array of Domain objects */ ],
  "nextLink": "https://api.purview-service.microsoft.com/datagovernance/catalog/businessdomains?api-version=2025-09-15-preview&$skipToken=abc123"
}
```

**Deleted records:** The `status` field on a domain can be `EXPIRED`. The API does not expose a separate delete feed — treat `EXPIRED` status as a soft delete signal. No hard-delete detection is available.

**Python read pattern:**
```python
import requests

def read_domains(endpoint, access_token):
    url = f"{endpoint}/datagovernance/catalog/businessdomains"
    params = {"api-version": "2025-09-15-preview"}
    headers = {"Authorization": f"Bearer {access_token}"}
    while url:
        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])
        url = data.get("nextLink")
        params = {}  # nextLink already contains all params
```

---

### Table: `data_products`

**Method:** GET
**URL:** `{endpoint}/datagovernance/catalog/dataProducts?api-version=2025-09-15-preview`

**Query parameters:**

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `api-version` | Yes | string | Must be `2025-09-15-preview` |
| `skip` | No | integer | Number of items to skip (offset-based pagination). |
| `top` | No | integer | Number of items to return per page. |
| `domainId` | No | string (uuid) | Filter to data products within a specific domain. |
| `orderBy` | No | string | Sort expression for results. |

**Pagination:** Uses offset-based pagination with `skip` and `top` parameters. The response also includes `nextLink` for convenience. Recommended approach: follow `nextLink` until it is absent.

**Example request (first page):**
```http
GET https://api.purview-service.microsoft.com/datagovernance/catalog/dataProducts?api-version=2025-09-15-preview&skip=0&top=100
Authorization: Bearer {access_token}
```

**Response envelope:**
```json
{
  "value": [ /* array of DataProduct objects */ ],
  "nextLink": "https://api.purview-service.microsoft.com/datagovernance/catalog/dataProducts?api-version=2025-09-15-preview&skip=100&top=100"
}
```

**Deleted records:** Similar to domains, `status: EXPIRED` is the soft-delete signal. No hard-delete detection endpoint is available.

**Python read pattern:**
```python
def read_data_products(endpoint, access_token, domain_id=None):
    url = f"{endpoint}/datagovernance/catalog/dataProducts"
    params = {"api-version": "2025-09-15-preview", "skip": 0, "top": 100}
    if domain_id:
        params["domainId"] = domain_id
    headers = {"Authorization": f"Bearer {access_token}"}
    while url:
        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])
        url = data.get("nextLink")
        params = {}  # nextLink already contains all params
```

---

### Table: `data_assets`

**Method:** POST
**URL:** `{endpoint}/datamap/api/search/query?api-version=2023-09-01`

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `keywords` | string | No | Full-text search keywords. Use `null` to return all assets. |
| `limit` | integer | No | Max results per page. Default: 50, Maximum: 1000. |
| `continuationToken` | string | No | Token for fetching the next page. `null` for first page. |
| `filter` | object | No | Filter expression (see filter operators below). |
| `orderby` | array | No | Sort order. Example: `[{"updateTime": "DESC"}]`. |
| `facets` | array | No | Facets for aggregation (not needed for data ingestion). |

**Filter operators for incremental sync:**
```json
{
  "attributeName": "modifiedTime",
  "operator": "ge",
  "attributeValue": 1704067200000
}
```
Where `attributeValue` is a Unix timestamp in milliseconds. Supported operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `contains`, `prefix`, `timerange`.

**Time range filter (alternative):**
```json
{
  "attributeName": "modifiedTime",
  "operator": "timerange",
  "attributeValue": "LAST_24H"
}
```
Supported time range values: `LAST_24H`, `LAST_7D`, `LAST_30D`, `LAST_365D`, `MORE_THAN_365D`.

**Example full-sync request (first page):**
```http
POST https://api.purview-service.microsoft.com/datamap/api/search/query?api-version=2023-09-01
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "keywords": null,
  "limit": 1000,
  "continuationToken": null
}
```

**Example incremental sync request:**
```http
POST https://api.purview-service.microsoft.com/datamap/api/search/query?api-version=2023-09-01
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "keywords": null,
  "limit": 1000,
  "filter": {
    "attributeName": "modifiedTime",
    "operator": "ge",
    "attributeValue": 1704067200000
  },
  "orderby": [{ "updateTime": "DESC" }]
}
```

**Pagination:** The response contains a `continuationToken` field. Pass this token as `continuationToken` in the next request body until the token is absent or null.

**Response envelope:**
```json
{
  "@search.count": 5155,
  "@search.count.approximate": true,
  "continuationToken": "<token>",
  "value": [ /* array of QueryResultValue objects */ ]
}
```

**Fetching full entity details:** The search query returns summary fields. To get full entity details including all attributes, classifications, and relationship attributes, call the Entity/Get endpoint per GUID:
```http
GET https://api.purview-service.microsoft.com/datamap/api/atlas/v2/entity/guid/{guid}?api-version=2023-09-01&minExtInfo=false&ignoreRelationships=false
Authorization: Bearer {access_token}
```

**Deleted records:** The Entity/Get endpoint returns `status: DELETED` for deleted entities. The search query can include deleted entities when filtering. To detect deletes during incremental sync, query deleted entities explicitly using a filter:
```json
{
  "filter": {
    "and": [
      { "entityType": "DataSet" },
      { "attributeName": "modifiedTime", "operator": "ge", "attributeValue": 1704067200000 }
    ]
  }
}
```
Then call Entity/Get per GUID to check the `status` field.

**Python read pattern (incremental):**
```python
def read_data_assets(endpoint, access_token, last_sync_time_ms=None):
    url = f"{endpoint}/datamap/api/search/query"
    params = {"api-version": "2023-09-01"}
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body = {"keywords": None, "limit": 1000, "continuationToken": None}
    if last_sync_time_ms:
        # subtract 1-hour lookback for clock skew
        lookback_ms = last_sync_time_ms - 3_600_000
        body["filter"] = {
            "attributeName": "modifiedTime",
            "operator": "ge",
            "attributeValue": lookback_ms
        }
    while True:
        resp = requests.post(url, params=params, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])
        token = data.get("continuationToken")
        if not token:
            break
        body["continuationToken"] = token
```

**Rate limits:** Microsoft does not publish explicit requests-per-second limits for the Purview Data Map API. The API returns HTTP 429 (Too Many Requests) when throttled. Implement exponential backoff starting at 1 second, retrying up to 3–5 times. The `Retry-After` header, when present, should be respected. Community implementations recommend no more than 10 concurrent requests.

---

## Field Type Mapping

### Unified Catalog API Types (domains, data_products)

| API Type | Python Type | Spark SQL Type | Notes |
|----------|-------------|----------------|-------|
| `string (uuid)` | `str` | `StringType` | UUIDs stored as strings. |
| `string` | `str` | `StringType` | General string fields. |
| `string (datetime)` | `str` → `datetime` | `TimestampType` | ISO 8601 format: `2025-01-15T10:00:00.000Z`. Parse with `datetime.fromisoformat()`. |
| `boolean` | `bool` | `BooleanType` | `true`/`false`. |
| `integer (int32)` | `int` | `IntegerType` | 32-bit signed integer. |
| `integer (int64)` | `int` | `LongType` | 64-bit signed integer. |
| `number (double)` | `float` | `DoubleType` | e.g., `dataQualityScore`. |
| `array of string` | `list[str]` | `ArrayType(StringType)` | e.g., `audience`. |
| `array of object` | `list[dict]` | `ArrayType(StructType)` | e.g., `contacts.owner`, `managedAttributes`. Flatten or serialize as JSON string. |
| `object` | `dict` | `StringType` (JSON) or `StructType` | e.g., `contacts`. Recommend serializing as JSON string for flexibility. |
| `string (enum)` | `str` | `StringType` | Values are constrained. Document allowed values in table description. |

### Data Map API Types (data_assets)

| API Type | Python Type | Spark SQL Type | Notes |
|----------|-------------|----------------|-------|
| `string` | `str` | `StringType` | General strings and UUIDs. |
| `integer (int64)` | `int` | `LongType` | `createTime`, `updateTime` are Unix timestamps in milliseconds. |
| `boolean` | `bool` | `BooleanType` | `isIncomplete`, `proxy`. |
| `integer (int32)` | `int` | `IntegerType` | `version`, `provenanceType`. |
| `array of string` | `list[str]` | `ArrayType(StringType)` | `labels`, `assetType`, `classification`. |
| `array of object` | `list[dict]` | `StringType` (JSON) | `meanings`, `classifications`, `contacts`. Complex nested objects — serialize as JSON. |
| `object` (attributes) | `dict` | `StringType` (JSON) or `MapType` | Attributes vary by `typeName`. Serialize as JSON string or use `MapType(StringType, StringType)`. |

**Special behaviors:**
- `updateTime` / `createTime` in Data Map entities are Unix epoch milliseconds (int64), not ISO 8601 strings. Convert with `datetime.utcfromtimestamp(value / 1000)`.
- `systemData.lastModifiedAt` in Unified Catalog entities is ISO 8601 with milliseconds: `2025-01-15T10:00:00.000Z`.
- `status` in `domains` and `data_products` uses uppercase enum values (`DRAFT`, `PUBLISHED`, `EXPIRED`).
- `status` in `data_assets` (AtlasEntity) uses uppercase values (`ACTIVE`, `DELETED`).
- The `attributes` field on `data_assets` is dynamic — keys depend on the `typeName`. Always check for key existence before accessing.

---

## Research Log

| Source Type | URL | Accessed (UTC) | Confidence | What it confirmed |
|-------------|-----|----------------|------------|-------------------|
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/unified-catalog-api-overview | 2026-04-01 | High | Unified Catalog API overview, supported resources, preview status |
| Official Docs | https://learn.microsoft.com/en-us/purview/data-gov-api-rest-data-plane | 2026-04-01 | High | Complete OAuth2 client credentials auth flow, token endpoint, required roles |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/operation-groups?view=rest-purview-purview-unified-catalog-2025-09-15-preview | 2026-04-01 | High | All Unified Catalog operation groups: Business Domain, Data Products, OKR, Terms, Policies, Critical Data Elements |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/business-domain/enumerate?view=rest-purview-purview-unified-catalog-2025-09-15-preview | 2026-04-01 | High | Domain enumerate endpoint URL, query params ($skipToken, writeOnly), full Domain schema, pagination via nextLink |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/business-domain/get?view=rest-purview-purview-unified-catalog-2025-09-15-preview | 2026-04-01 | High | Domain get endpoint URL, path params (domainId), full Domain schema cross-check |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/data-products/list?view=rest-purview-purview-unified-catalog-2025-09-15-preview | 2026-04-01 | High | Data Products list endpoint, query params (skip, top, domainId, orderBy), full DataProduct schema, nextLink pagination |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/data-products/get?view=rest-purview-purview-unified-catalog-2025-09-15-preview | 2026-04-01 | High | Data Products get endpoint, full DataProduct schema cross-check |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/purview-unified-catalog/data-products/list-relationships?view=rest-purview-purview-unified-catalog-2025-09-15-preview | 2026-04-01 | High | DataProductRelationship schema, EntityCategory enum (DATAASSET, DOMAIN, TERM, etc.) |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/datamapdataplane/discovery/query?view=rest-purview-datamapdataplane-2023-09-01 | 2026-04-01 | High | Discovery Query POST endpoint, request body schema (keywords, limit, continuationToken, filter, orderby, facets), QueryResultValue fields, continuationToken pagination, filter operators including modifiedTime |
| Official Docs | https://learn.microsoft.com/en-us/rest/api/purview/datamapdataplane/entity/get?view=rest-purview-datamapdataplane-2023-09-01 | 2026-04-01 | High | Entity Get endpoint, full AtlasEntity schema (all fields: guid, typeName, status, createTime, updateTime, attributes, classifications, contacts, labels, meanings, businessAttributes, relationshipAttributes) |
| Official Docs | https://learn.microsoft.com/en-us/purview/data-gov-api-create-assets | 2026-04-01 | High | Atlas v2 entity endpoint URL patterns (classic vs new portal), entity structure for create (confirms attribute structure) |

---

## Known Quirks and Caveats

1. **Unified Catalog API is in Public Preview (as of October 2025).** The `api-version: 2025-09-15-preview` suffix signals preview status. Breaking changes are possible before GA. Monitor the Microsoft Purview release notes.

2. **Data assets are NOT in the Unified Catalog API.** The Unified Catalog API documentation explicitly states: "Data asset and critical data column APIs for Unified Catalog are on our roadmap." For `data_assets`, use the Data Map API (`datamap/api/atlas/v2` or `datamap/api/search/query`).

3. **Two base URL patterns exist.** The new Purview portal uses `https://api.purview-service.microsoft.com/`. The classic portal uses `https://{accountName}.purview.azure.com/`. The connector should parameterize the endpoint and default to the new portal URL.

4. **Token resource parameter is `https://purview.azure.net`** (not `https://api.purview-service.microsoft.com`). Using an incorrect `resource` value will result in an invalid token.

5. **Domains `enumerate` uses `$skipToken`, while data_products `list` uses `skip`/`top`.** These are different pagination mechanisms on the same API surface — handle each table's pagination separately.

6. **Search query `@search.count.approximate`** may be `true` when there are more than 1000 results in the Data Map — exact count is not guaranteed. Always paginate via `continuationToken` regardless of the count value.

7. **`data_assets` attributes are schema-less and vary by `entityType`.** A `snowflake_table` has different `attributes` keys than an `azure_blob_path`. The connector should store the `attributes` field as a serialized JSON string in the `data_assets` table rather than attempting to flatten all possible attribute schemas.

8. **No explicit rate limits are documented** for either the Unified Catalog API or the Data Map API. Implement retry logic with exponential backoff on HTTP 429 responses. Respect the `Retry-After` response header when present.

9. **Service principal creation guidance:** Microsoft documentation warns that reusing existing service principals has a high failure rate. Create a dedicated new service principal for this connector.

10. **`writeOnly` parameter on domain enumerate** — set to `false` or omit it. If set to `true`, only domains with write permission will be returned, which is not appropriate for a read-only data ingestion connector.
