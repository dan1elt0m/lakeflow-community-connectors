"""Schemas, metadata, and constants for the Microsoft Purview connector."""

from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

RETRIABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0  # seconds; doubled after each retry
REQUEST_TIMEOUT = 30  # seconds

UNIFIED_CATALOG_API_VERSION = "2025-09-15-preview"
DATA_MAP_API_VERSION = "2023-09-01"

UNIFIED_CATALOG_BASE_URL = "https://api.purview-service.microsoft.com"
PURVIEW_TOKEN_SCOPE = "https://purview.azure.net/.default"
PURVIEW_TOKEN_RESOURCE = "https://purview.azure.net"

# ---------- systemData struct (shared by domains and data_products) ----------

SYSTEM_DATA_STRUCT = StructType(
    [
        StructField("createdAt", TimestampType(), nullable=True),
        StructField("createdBy", StringType(), nullable=True),
        StructField("lastModifiedAt", TimestampType(), nullable=True),
        StructField("lastModifiedBy", StringType(), nullable=True),
        StructField("expiredAt", TimestampType(), nullable=True),
        StructField("expiredBy", StringType(), nullable=True),
    ]
)

# ---------- domains schema ----------

PARENT_COLLECTION_STRUCT = StructType(
    [
        StructField("refName", StringType(), nullable=True),
        StructField("type", StringType(), nullable=True),
    ]
)

RELATED_COLLECTION_STRUCT = StructType(
    [
        StructField("name", StringType(), nullable=True),
        StructField("friendlyName", StringType(), nullable=True),
        StructField("parentCollection", PARENT_COLLECTION_STRUCT, nullable=True),
    ]
)

PLATFORM_DOMAIN_STRUCT = StructType(
    [
        StructField("name", StringType(), nullable=True),
        StructField("friendlyName", StringType(), nullable=True),
        StructField(
            "relatedCollections",
            ArrayType(RELATED_COLLECTION_STRUCT),
            nullable=True,
        ),
    ]
)

MANAGED_ATTRIBUTE_STRUCT = StructType(
    [
        StructField("name", StringType(), nullable=True),
        StructField("value", StringType(), nullable=True),
        StructField("isRequired", BooleanType(), nullable=True),
    ]
)

DOMAINS_SCHEMA = StructType(
    [
        StructField("id", StringType(), nullable=False),
        StructField("name", StringType(), nullable=False),
        StructField("description", StringType(), nullable=True),
        StructField("parentId", StringType(), nullable=True),
        StructField("status", StringType(), nullable=False),
        StructField("type", StringType(), nullable=False),
        StructField("isRestricted", BooleanType(), nullable=True),
        StructField(
            "thumbnail",
            StructType([StructField("color", StringType(), nullable=True)]),
            nullable=True,
        ),
        StructField("domains", ArrayType(PLATFORM_DOMAIN_STRUCT), nullable=True),
        StructField(
            "managedAttributes",
            ArrayType(MANAGED_ATTRIBUTE_STRUCT),
            nullable=True,
        ),
        StructField("systemData", SYSTEM_DATA_STRUCT, nullable=True),
    ]
)

DOMAINS_METADATA = {
    "primary_keys": ["id"],
    "cursor_field": "",
    "ingestion_type": "snapshot",
}

# ---------- data_products schema ----------

CONTACT_ENTRY_STRUCT = StructType(
    [
        StructField("id", StringType(), nullable=True),
        StructField("description", StringType(), nullable=True),
    ]
)

CONTACTS_STRUCT = StructType(
    [
        StructField("owner", ArrayType(CONTACT_ENTRY_STRUCT), nullable=True),
        StructField("expert", ArrayType(CONTACT_ENTRY_STRUCT), nullable=True),
        StructField("databaseAdmin", ArrayType(CONTACT_ENTRY_STRUCT), nullable=True),
    ]
)

LINK_STRUCT = StructType(
    [
        StructField("url", StringType(), nullable=True),
        StructField("name", StringType(), nullable=True),
        StructField("dataAssetId", StringType(), nullable=True),
    ]
)

ADDITIONAL_PROPERTIES_STRUCT = StructType(
    [
        StructField("assetCount", LongType(), nullable=True),
    ]
)

DATA_PRODUCTS_SCHEMA = StructType(
    [
        StructField("id", StringType(), nullable=False),
        StructField("name", StringType(), nullable=False),
        StructField("domain", StringType(), nullable=False),
        StructField("type", StringType(), nullable=False),
        StructField("description", StringType(), nullable=True),
        StructField("businessUse", StringType(), nullable=True),
        StructField("status", StringType(), nullable=False),
        StructField("endorsed", BooleanType(), nullable=False),
        StructField("updateFrequency", StringType(), nullable=True),
        StructField("sensitivityLabel", StringType(), nullable=True),
        StructField("dataQualityScore", DoubleType(), nullable=True),
        StructField("activeSubscriberCount", LongType(), nullable=True),
        StructField("audience", ArrayType(StringType()), nullable=True),
        StructField("contacts", CONTACTS_STRUCT, nullable=True),
        StructField("termsOfUse", ArrayType(LINK_STRUCT), nullable=True),
        StructField("documentation", ArrayType(LINK_STRUCT), nullable=True),
        StructField(
            "managedAttributes",
            ArrayType(MANAGED_ATTRIBUTE_STRUCT),
            nullable=True,
        ),
        StructField("additionalProperties", ADDITIONAL_PROPERTIES_STRUCT, nullable=True),
        StructField("systemData", SYSTEM_DATA_STRUCT, nullable=True),
    ]
)

DATA_PRODUCTS_METADATA = {
    "primary_keys": ["id"],
    "cursor_field": "",
    "ingestion_type": "snapshot",
}

# ---------- data_assets schema (from search query results) ----------

TERM_STRUCT = StructType(
    [
        StructField("name", StringType(), nullable=True),
        StructField("glossaryName", StringType(), nullable=True),
        StructField("guid", StringType(), nullable=True),
    ]
)

ASSET_CONTACT_STRUCT = StructType(
    [
        StructField("id", StringType(), nullable=True),
        StructField("info", StringType(), nullable=True),
        StructField("contactType", StringType(), nullable=True),
    ]
)

DATA_ASSETS_SCHEMA = StructType(
    [
        StructField("id", StringType(), nullable=False),
        StructField("qualifiedName", StringType(), nullable=False),
        StructField("name", StringType(), nullable=False),
        StructField("description", StringType(), nullable=True),
        StructField("owner", StringType(), nullable=True),
        StructField("entityType", StringType(), nullable=False),
        StructField("assetType", ArrayType(StringType()), nullable=True),
        StructField("classification", ArrayType(StringType()), nullable=True),
        StructField("label", ArrayType(StringType()), nullable=True),
        StructField("term", ArrayType(TERM_STRUCT), nullable=True),
        StructField("contact", ArrayType(ASSET_CONTACT_STRUCT), nullable=True),
        StructField("createTime", LongType(), nullable=True),
        StructField("updateTime", LongType(), nullable=True),
        StructField("endorsement", StringType(), nullable=True),
    ]
)

DATA_ASSETS_METADATA = {
    "primary_keys": ["id"],
    "cursor_field": "updateTime",
    "ingestion_type": "cdc",
}

# ---------- table registry ----------

TABLE_SCHEMAS = {
    "domains": DOMAINS_SCHEMA,
    "data_products": DATA_PRODUCTS_SCHEMA,
    "data_assets": DATA_ASSETS_SCHEMA,
}

TABLE_METADATA = {
    "domains": DOMAINS_METADATA,
    "data_products": DATA_PRODUCTS_METADATA,
    "data_assets": DATA_ASSETS_METADATA,
}
