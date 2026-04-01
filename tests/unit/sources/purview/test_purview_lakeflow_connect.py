"""Tests for PurviewLakeflowConnect.

Runs the full LakeflowConnectTests suite plus SupportsPartitionedStreamTests
against the real Microsoft Purview API. Requires configs/dev_config.json
and an active Azure login (az login) for DefaultAzureCredential.
"""

from databricks.labs.community_connector.sources.purview.purview import (
    PurviewLakeflowConnect,
)
from tests.unit.sources.test_partition_suite import SupportsPartitionedStreamTests
from tests.unit.sources.test_suite import LakeflowConnectTests


class TestPurviewConnector(LakeflowConnectTests, SupportsPartitionedStreamTests):
    connector_class = PurviewLakeflowConnect
    sample_records = 50
