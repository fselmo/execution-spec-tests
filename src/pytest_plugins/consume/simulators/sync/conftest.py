"""
Pytest fixtures for the `consume engine_sync` simulator.

Configures the hive back-end & EL clients for each individual test execution.
"""

import io
import json
from typing import Generator, Mapping, cast

import pytest
from hive.client import Client, ClientType
from hive.testing import HiveTest

from ethereum_test_base_types import Number, to_json
from ethereum_test_exceptions import ExceptionMapper
from ethereum_test_fixtures import BlockchainEngineSyncFixture
from ethereum_test_rpc import EngineRPC, EthRPC

pytest_plugins = (
    "pytest_plugins.pytest_hive.pytest_hive",
    "pytest_plugins.consume.simulators.base",
    "pytest_plugins.consume.simulators.single_test_client",
    "pytest_plugins.consume.simulators.test_case_description",
    "pytest_plugins.consume.simulators.timing_data",
    "pytest_plugins.consume.simulators.exceptions",
)


def pytest_configure(config):
    """Set the supported fixture formats for the engine sync simulator."""
    config._supported_fixture_formats = [BlockchainEngineSyncFixture.format_name]


@pytest.fixture(scope="function")
def engine_rpc(client: Client, client_exception_mapper: ExceptionMapper | None) -> EngineRPC:
    """Initialize engine RPC client for the execution client under test."""
    if client_exception_mapper:
        return EngineRPC(
            f"http://{client.ip}:8551",
            response_validation_context={
                "exception_mapper": client_exception_mapper,
            },
        )
    return EngineRPC(f"http://{client.ip}:8551")


@pytest.fixture(scope="function")
def eth_rpc(client: Client) -> EthRPC:
    """Initialize eth RPC client for the execution client under test."""
    return EthRPC(f"http://{client.ip}:8545")


@pytest.fixture(scope="function")
def sync_genesis(fixture: BlockchainEngineSyncFixture) -> dict:
    """Convert the fixture genesis block header and pre-state to a sync client genesis state."""
    genesis = to_json(fixture.genesis)
    alloc = to_json(fixture.pre)
    # NOTE: nethermind requires account keys without '0x' prefix
    genesis["alloc"] = {k.replace("0x", ""): v for k, v in alloc.items()}
    return genesis


@pytest.fixture(scope="function")
def sync_buffered_genesis(sync_genesis: dict) -> io.BufferedReader:
    """Create a buffered reader for the genesis block header of the sync client."""
    genesis_json = json.dumps(sync_genesis)
    genesis_bytes = genesis_json.encode("utf-8")
    return io.BufferedReader(cast(io.RawIOBase, io.BytesIO(genesis_bytes)))


@pytest.fixture(scope="function")
def sync_client_files(sync_buffered_genesis: io.BufferedReader) -> Mapping[str, io.BufferedReader]:
    """Define the files that hive will start the sync client with."""
    files = {}
    files["/genesis.json"] = sync_buffered_genesis
    return files


@pytest.fixture(scope="function")
def sync_client(
    hive_test: HiveTest,
    client: Client,  # The main client under test
    sync_client_files: dict,
    environment: dict,
    client_type: ClientType,  # This will be the same client type for now
) -> Generator[Client, None, None]:
    """Start a sync client that will sync from the client under test."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Starting sync client setup for {client_type.name}")
    
    # Wait a bit for the client to be fully ready
    import time
    time.sleep(2)
    
    # Get the enode URL from the client under test
    try:
        client_enode = client.enode()
        logger.info(f"Got enode from client: {client_enode}")
        
        # Replace localhost/127.0.0.1 with the actual client IP for container communication
        enode_str = str(client_enode)
        if "127.0.0.1" in enode_str or "localhost" in enode_str:
            enode_str = enode_str.replace("127.0.0.1", client.ip).replace("localhost", client.ip)
            logger.info(f"Updated enode for container communication: {enode_str}")
        
    except Exception as e:
        logger.error(f"Failed to get enode: {e}")
        raise

    # Update environment to include bootnode
    sync_environment = environment.copy()
    sync_environment["HIVE_BOOTNODE"] = enode_str

    logger.info(f"Starting sync client with bootnode: {enode_str}")
    logger.info(f"Sync client files: {list(sync_client_files.keys())}")
    
    # For now, use the same client type as the main client
    # In the future, this can be parametrized separately
    sync_client = hive_test.start_client(
        client_type=client_type,
        environment=sync_environment,
        files=sync_client_files,
    )

    error_message = (
        f"Unable to start sync client ({client_type.name}) via Hive. "
        "Check the client or Hive server logs for more information."
    )
    assert sync_client is not None, error_message

    yield sync_client

    # Cleanup
    sync_client.stop()


@pytest.fixture(scope="function")
def sync_engine_rpc(sync_client: Client) -> EngineRPC:
    """Initialize engine RPC client for the sync client."""
    return EngineRPC(f"http://{sync_client.ip}:8551")


@pytest.fixture(scope="function")
def sync_eth_rpc(sync_client: Client) -> EthRPC:
    """Initialize eth RPC client for the sync client."""
    return EthRPC(f"http://{sync_client.ip}:8545")


@pytest.fixture(scope="module")
def test_suite_name() -> str:
    """The name of the hive test suite used in this simulator."""
    return "eest/consume-sync"


@pytest.fixture(scope="module")
def test_suite_description() -> str:
    """The description of the hive test suite used in this simulator."""
    return "Execute blockchain sync tests against clients using the Engine API."


@pytest.fixture(scope="function")
def client_files(buffered_genesis: io.BufferedReader) -> Mapping[str, io.BufferedReader]:
    """Define the files that hive will start the client with."""
    files = {}
    files["/genesis.json"] = buffered_genesis
    return files
