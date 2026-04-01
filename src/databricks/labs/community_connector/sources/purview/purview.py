"""Microsoft Purview connector for Lakeflow Community Connectors.

Ingests three tables from the Microsoft Purview governance APIs:
  - domains       (Unified Catalog API, snapshot)
  - data_products (Unified Catalog API, snapshot)
  - data_assets   (Data Map search/query API, CDC via modifiedTime filter)

Authentication supports two modes:
  - default_credential: uses azure-identity DefaultAzureCredential
  - client_secret: explicit OAuth2 client credentials flow
"""

import time
from datetime import datetime, timezone
from typing import Iterator, Sequence

import requests
from pyspark.sql.types import StructType

from databricks.labs.community_connector.interface import LakeflowConnect
from databricks.labs.community_connector.interface.supports_partition import (
    SupportsPartitionedStream,
)
from databricks.labs.community_connector.sources.purview.purview_schemas import (
    DATA_MAP_API_VERSION,
    INITIAL_BACKOFF,
    MAX_RETRIES,
    PURVIEW_TOKEN_RESOURCE,
    PURVIEW_TOKEN_SCOPE,
    REQUEST_TIMEOUT,
    RETRIABLE_STATUS_CODES,
    TABLE_METADATA,
    TABLE_SCHEMAS,
    UNIFIED_CATALOG_API_VERSION,
    UNIFIED_CATALOG_BASE_URL,
)

_TABLES = ["domains", "data_products", "data_assets"]

# Default lookback for data_assets incremental reads: 1 hour in ms.
_LOOKBACK_MS = 3_600_000


class PurviewLakeflowConnect(LakeflowConnect, SupportsPartitionedStream):
    """LakeflowConnect + SupportsPartitionedStream implementation for Microsoft Purview."""

    def __init__(self, options: dict[str, str]) -> None:
        super().__init__(options)
        self._account_name = options["purview_account_name"]
        self._auth_method = options.get("auth_method", "default_credential")

        # Resolved lazily and cached.
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        # Cap cursors at init time so a trigger never chases new data.
        self._init_ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Track whether lookback has been applied in the current trigger for data_assets.
        self._lookback_applied = False

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """Return a valid bearer token, refreshing if expired."""
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        if self._auth_method == "client_secret":
            self._access_token = self._get_token_client_secret()
        else:
            self._access_token = self._get_token_default_credential()

        return self._access_token

    def _get_token_default_credential(self) -> str:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        token = credential.get_token(PURVIEW_TOKEN_SCOPE)
        self._token_expires_at = token.expires_on
        return token.token

    def _get_token_client_secret(self) -> str:
        tenant_id = self.options["tenant_id"]
        client_id = self.options["client_id"]
        client_secret = self.options["client_secret"]

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "resource": PURVIEW_TOKEN_RESOURCE,
        }
        resp = requests.post(token_url, data=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
        self._token_expires_at = time.time() + int(body.get("expires_in", 3600))
        return body["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Base URLs
    # ------------------------------------------------------------------

    @property
    def _unified_catalog_url(self) -> str:
        return UNIFIED_CATALOG_BASE_URL

    @property
    def _data_map_url(self) -> str:
        return f"https://{self._account_name}.purview.azure.com"

    # ------------------------------------------------------------------
    # HTTP helper with retry
    # ------------------------------------------------------------------

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """Issue an HTTP request with exponential backoff on retriable errors."""
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        backoff = INITIAL_BACKOFF
        resp = None
        for attempt in range(MAX_RETRIES):
            headers = self._headers()
            if method == "GET":
                resp = requests.get(url, headers=headers, **kwargs)
            elif method == "POST":
                resp = requests.post(url, headers=headers, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if resp.status_code not in RETRIABLE_STATUS_CODES:
                return resp

            # Respect Retry-After header if present.
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else backoff

            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
                backoff *= 2

        return resp  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # LakeflowConnect interface
    # ------------------------------------------------------------------

    def list_tables(self) -> list[str]:
        return list(_TABLES)

    def get_table_schema(self, table_name: str, table_options: dict[str, str]) -> StructType:
        self._validate_table(table_name)
        return TABLE_SCHEMAS[table_name]

    def read_table_metadata(self, table_name: str, table_options: dict[str, str]) -> dict:
        self._validate_table(table_name)
        return dict(TABLE_METADATA[table_name])

    def read_table(
        self,
        table_name: str,
        start_offset: dict,
        table_options: dict[str, str],
    ) -> tuple[Iterator[dict], dict]:
        """Read records. Used by simpleStreamReader for snapshot tables
        and as fallback for data_assets."""
        self._validate_table(table_name)

        if table_name == "domains":
            return self._read_domains()
        elif table_name == "data_products":
            return self._read_data_products()
        elif table_name == "data_assets":
            return self._read_data_assets_incremental(start_offset, table_options)
        else:
            raise ValueError(f"Unknown table: {table_name}")

    # ------------------------------------------------------------------
    # SupportsPartitionedStream interface
    # ------------------------------------------------------------------

    def is_partitioned(self, table_name: str) -> bool:
        """Only data_assets uses partitioned streaming."""
        return table_name == "data_assets"

    def latest_offset(
        self,
        table_name: str,
        table_options: dict[str, str],
        start_offset: dict | None = None,
    ) -> dict:
        """Return the current high-water mark for data_assets.

        This is a lightweight call -- we use the current wall-clock time
        (capped at init time) as the latest offset rather than querying
        the API, since data_assets uses modifiedTime range queries.
        """
        if table_name != "data_assets":
            raise ValueError(f"latest_offset not supported for non-partitioned table: {table_name}")

        # The latest available offset is the init timestamp.
        return {"cursor_ms": self._init_ts_ms}

    def get_partitions(
        self,
        table_name: str,
        table_options: dict[str, str],
        start_offset: dict | None = None,
        end_offset: dict | None = None,
    ) -> Sequence[dict]:
        """Split data_assets time range into partitions for parallel reads."""
        if table_name != "data_assets":
            raise ValueError(
                f"get_partitions not supported for non-partitioned table: {table_name}"
            )

        # Batch mode: partition the entire table as a single partition.
        if start_offset is None and end_offset is None:
            return [{"since_ms": 0, "until_ms": self._init_ts_ms}]

        if start_offset == end_offset:
            return []

        start_ms = (start_offset or {}).get("cursor_ms", 0)
        end_ms = (end_offset or {}).get("cursor_ms", self._init_ts_ms)

        if start_ms >= end_ms:
            return []

        # First streaming micro-batch (start_offset is None): return a single
        # partition covering the full range to avoid generating thousands of
        # daily windows from epoch.
        if start_offset is None:
            return [{"since_ms": start_ms, "until_ms": end_ms}]

        # Split the range into windows. The window size is configurable
        # via table_options["window_seconds"] (default: 86400 = 1 day).
        window_ms = int(table_options.get("window_seconds", "86400")) * 1000

        partitions = []
        current = start_ms
        while current < end_ms:
            partition_end = min(current + window_ms, end_ms)
            partitions.append({"since_ms": current, "until_ms": partition_end})
            current = partition_end

        return partitions

    def read_partition(
        self,
        table_name: str,
        partition: dict,
        table_options: dict[str, str],
    ) -> Iterator[dict]:
        """Read data_assets for a single time-range partition.

        Runs on executors -- re-creates auth and fetches data independently.
        """
        if table_name != "data_assets":
            raise ValueError(
                f"read_partition not supported for non-partitioned table: {table_name}"
            )

        since_ms = partition["since_ms"]
        until_ms = partition["until_ms"]
        limit = int(table_options.get("page_size", "1000"))
        max_records = int(table_options.get("max_records_per_batch", "10000"))

        # Apply lookback on the since side.
        query_since_ms = max(0, since_ms - _LOOKBACK_MS) if since_ms > 0 else 0

        url = f"{self._data_map_url}/datamap/api/search/query"
        params = {"api-version": DATA_MAP_API_VERSION}

        filter_clauses = []
        if query_since_ms > 0:
            filter_clauses.append(
                {
                    "attributeName": "modifiedTime",
                    "operator": "ge",
                    "attributeValue": query_since_ms,
                }
            )
        if until_ms < self._init_ts_ms:
            filter_clauses.append(
                {
                    "attributeName": "modifiedTime",
                    "operator": "le",
                    "attributeValue": until_ms,
                }
            )

        search_filter: dict | None = None
        if len(filter_clauses) == 1:
            search_filter = filter_clauses[0]
        elif len(filter_clauses) > 1:
            search_filter = {"and": filter_clauses}

        body: dict = {
            "keywords": None,
            "limit": limit,
            "continuationToken": None,
        }
        if search_filter:
            body["filter"] = search_filter

        records: list[dict] = []
        while True:
            resp = self._request_with_retry("POST", url, params=params, json=body)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to query data_assets: {resp.status_code} {resp.text}")
            data = resp.json()
            batch = data.get("value", [])
            for item in batch:
                records.append(self._normalize_asset(item))

            if len(records) >= max_records:
                break

            token = data.get("continuationToken")
            if not token:
                break
            body["continuationToken"] = token

        return iter(records)

    # ------------------------------------------------------------------
    # Snapshot readers (domains, data_products)
    # ------------------------------------------------------------------

    def _read_domains(self) -> tuple[Iterator[dict], dict]:
        """Full snapshot read of all business domains."""
        url = f"{self._unified_catalog_url}/datagovernance/catalog/businessdomains"
        params: dict[str, str] = {"api-version": UNIFIED_CATALOG_API_VERSION}

        records: list[dict] = []
        while url:
            resp = self._request_with_retry("GET", url, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to read domains: {resp.status_code} {resp.text}")
            data = resp.json()
            for item in data.get("value", []):
                records.append(self._normalize_system_data(item))
            url = data.get("nextLink")
            params = {}  # nextLink already contains query params

        return iter(records), {}

    def _read_data_products(self) -> tuple[Iterator[dict], dict]:
        """Full snapshot read of all data products."""
        url = f"{self._unified_catalog_url}/datagovernance/catalog/dataProducts"
        params: dict[str, str] = {
            "api-version": UNIFIED_CATALOG_API_VERSION,
            "skip": "0",
            "top": "100",
        }

        records: list[dict] = []
        while url:
            resp = self._request_with_retry("GET", url, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to read data_products: {resp.status_code} {resp.text}")
            data = resp.json()
            for item in data.get("value", []):
                records.append(self._normalize_system_data(item))
            url = data.get("nextLink")
            params = {}  # nextLink already contains query params

        return iter(records), {}

    # ------------------------------------------------------------------
    # Incremental reader for data_assets (used by simpleStreamReader fallback)
    # ------------------------------------------------------------------

    def _read_data_assets_incremental(
        self, start_offset: dict, table_options: dict[str, str]
    ) -> tuple[Iterator[dict], dict]:
        """Sliding time-window incremental read for data_assets.

        Used when the table falls back to simpleStreamReader (non-partitioned path).
        """
        since_ms = start_offset.get("cursor_ms") if start_offset else None
        if since_ms is None:
            # Try user-supplied start_timestamp (Unix ms).
            start_ts = table_options.get("start_timestamp")
            if start_ts:
                since_ms = int(start_ts)
            else:
                since_ms = 0

        # Short-circuit if already caught up.
        if since_ms >= self._init_ts_ms:
            return iter([]), start_offset or {}

        max_records = int(table_options.get("max_records_per_batch", "10000"))
        limit = int(table_options.get("page_size", "1000"))

        # Initial load (since_ms == 0): full scan with no time filter.
        # Incremental loads: use a sliding time window.
        is_initial = since_ms == 0
        if is_initial:
            until_ms = self._init_ts_ms
        else:
            window_ms = int(table_options.get("window_seconds", "86400")) * 1000
            until_ms = min(since_ms + window_ms, self._init_ts_ms)

        # Apply lookback only on the first call of the trigger.
        query_since_ms = since_ms
        if not self._lookback_applied and since_ms > 0:
            query_since_ms = max(0, since_ms - _LOOKBACK_MS)
            self._lookback_applied = True

        url = f"{self._data_map_url}/datamap/api/search/query"
        params = {"api-version": DATA_MAP_API_VERSION}

        # Build filter: no time filter for initial load, time-bounded for incremental.
        search_filter: dict | None = None
        if not is_initial:
            filter_clauses = []
            if query_since_ms > 0:
                filter_clauses.append(
                    {
                        "attributeName": "modifiedTime",
                        "operator": "ge",
                        "attributeValue": query_since_ms,
                    }
                )
            filter_clauses.append(
                {
                    "attributeName": "modifiedTime",
                    "operator": "le",
                    "attributeValue": until_ms,
                }
            )
            search_filter = (
                filter_clauses[0] if len(filter_clauses) == 1 else {"and": filter_clauses}
            )

        body: dict = {
            "keywords": None,
            "limit": limit,
            "continuationToken": None,
        }
        if search_filter:
            body["filter"] = search_filter

        records: list[dict] = []
        while True:
            resp = self._request_with_retry("POST", url, params=params, json=body)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to query data_assets: {resp.status_code} {resp.text}")
            data = resp.json()
            batch = data.get("value", [])
            for item in batch:
                records.append(self._normalize_asset(item))

            if len(records) >= max_records:
                break

            token = data.get("continuationToken")
            if not token:
                break
            body["continuationToken"] = token

        # Advance cursor to window end regardless of whether records were found,
        # so the next call slides forward.
        end_offset = {"cursor_ms": until_ms}
        if start_offset and start_offset == end_offset:
            return iter([]), start_offset

        return iter(records), end_offset

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_timestamp(value: str | None) -> str | None:
        """Truncate high-precision ISO timestamps to microseconds (6 fractional digits).

        Purview returns up to 7 fractional digits (e.g. '2026-01-21T14:04:56.3431776Z')
        but Spark TimestampType only supports up to 6.
        """
        if value is None:
            return None
        # Match pattern like .1234567Z and truncate to .123456Z
        if "." in value and value.endswith("Z"):
            dot_idx = value.index(".")
            frac = value[dot_idx + 1 : -1]  # digits between . and Z
            if len(frac) > 6:
                frac = frac[:6]
            return value[: dot_idx + 1] + frac + "Z"
        return value

    @staticmethod
    def _normalize_system_data(record: dict) -> dict:
        """Normalize systemData timestamps in a record to be Spark-compatible."""
        sys_data = record.get("systemData")
        if isinstance(sys_data, dict):
            ts_fields = ["createdAt", "lastModifiedAt", "expiredAt"]
            for field in ts_fields:
                if field in sys_data:
                    sys_data[field] = PurviewLakeflowConnect._normalize_timestamp(sys_data[field])
        return record

    @staticmethod
    def _normalize_asset(item: dict) -> dict:
        """Normalize a search query result into a flat record matching DATA_ASSETS_SCHEMA."""
        return {
            "id": item.get("id"),
            "qualifiedName": item.get("qualifiedName"),
            "name": item.get("name"),
            "description": item.get("description"),
            "owner": item.get("owner"),
            "entityType": item.get("entityType"),
            "assetType": item.get("assetType"),
            "classification": item.get("classification"),
            "label": item.get("label"),
            "term": item.get("term"),
            "contact": item.get("contact"),
            "createTime": item.get("createTime"),
            "updateTime": item.get("updateTime"),
            "endorsement": item.get("endorsement"),
        }

    def _validate_table(self, table_name: str) -> None:
        if table_name not in _TABLES:
            raise ValueError(f"Table '{table_name}' is not supported. Supported tables: {_TABLES}")
