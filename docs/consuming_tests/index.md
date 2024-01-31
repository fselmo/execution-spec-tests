# Consuming Tests (Fixtures) Generated by execution-spec-tests

@ethereum/execution-spec-tests generates JSON test fixtures in different formats that can be consumed by execution clients either directly or via Hive:

| Format | Consumed by the client | Location in `.tar.gz` release |
| --- | --- | --- |
| [State Tests](./state_test.md) | directly via a `statetest`-like command<br/> (e.g., [go-ethereum/cmd/evm/staterunner.go](https://github.com/ethereum/go-ethereum/blob/509a64ffb9405942396276ae111d06f9bded9221/cmd/evm/staterunner.go#L35)) | `./fixtures/state_tests/` |
| [Blockchain Tests](./blockchain_test.md) | directly via a `blocktest`-like command<br/> (e.g., [go-ethereum/cmd/evm/blockrunner.go](https://github.com/ethereum/go-ethereum/blob/509a64ffb9405942396276ae111d06f9bded9221/cmd/evm/blockrunner.go#L39)) | `./fixtures/blockchain_tests/` |
| [Blockchain Hive Tests](./blockchain_test_hive.md) | in the [Hive `pyspec` simulator](https://github.com/ethereum/hive/tree/master/simulators/ethereum/pyspec#readme) via the Engine API and other RPC endpoints  | `./fixtures/blockchain_tests_hive/` |

Here's a top-level comparison of the different methods of consuming tests:

| Consumed via | Scope | Pros | Cons |
| --- | --- | --- | --- |
| `statetest` or <code>blocktest</code>-like command | Module test | - Fast feedback loop<br/>- Less complex | - Smaller coverage scope<br/>- Requires a dedicated interface to the client EVM to consume the JSON fixtures and execute tests |
| `hive --sim ethereum/pyspec` | System test / Integration test | - Wider Coverage Scope<br/>- Tests more of the client stack | - Slower feedback loop<br/>- Harder to debug<br/>- Post-Merge forks only (requires the Engine API) |

!!! note "Running `blocktest`, `statetest`, directly within the execution-spec-tests framework"

    It's possible to execute `evm blocktest` directly within the execution-spec-tests framework. This is intended to verify fixture generation, see [Debugging `t8n` Tools](../getting_started/debugging_t8n_tools.md).

!!! note "Generating test fixtures using a `t8n` tool via `fill` is not considered to be the actual test"

    The `fill` command uses `t8n` tools to generate fixtures. Whilst this will provide basic sanity checking of EVM behavior and a sub-set of post conditions are typically checked within test cases, it is not considered the actual test. The actual test is the execution of the fixture against the EVM which will check the entire post allocation and typically use different code paths than `t8n` commands.

## Release Formats

The @ethereum/execution-spec-tests repository provides [releases](https://github.com/ethereum/execution-spec-tests/releases) of fixtures in various formats (as of 2023-10-16):

| Release Artifact               | Consumer | Fork/feature scope |
| ------------------------------ | -------- | ------------------ |
| `fixtures.tar.gz`              | Clients  | All tests until the last stable fork | "Must pass" |
| `fixtures_develop.tar.gz`      | Clients  | All tests until the last development fork |

## Obtaining the Most Recent Release Artifacts

Artifacts can be downloaded directly from [the release page](https://github.com/ethereum/execution-spec-tests/releases). The following script demonstrates how the most recent release version of a specific artifact can be downloaded using the Github API:

```bash
#!/bin/bash

# requires jq
# sudo apt install jq

# The following two artifacts are intended for consumption by clients:
# - fixtures.tar.gz: Generated up to the last deployed fork.
# - fixtures_develop.tar.gz: Generated up to and including the latest dev fork.
# As of Oct 2023, dev is Cancun, deployed is Shanghai.

ARTIFACT="fixtures_develop.tar.gz"  

OWNER="ethereum"
REPO="execution-spec-tests"

DOWNLOAD_URL=$(curl -s https://api.github.com/repos/$OWNER/$REPO/releases/latest \
                   | jq -r '.assets[] | select(.name=="'$ARTIFACT'").browser_download_url')

# Sanity check for the download URL: contains a version tag prefixed with "v"
if [[ "$DOWNLOAD_URL" =~ v[0-9]+\.[0-9]+\.[0-9]+ ]]; then
    curl -LO $DOWNLOAD_URL
else
    echo "Error: URL does not contain a valid version tag (URL: ${DOWNLOAD_URL})."
    exit 1
fi
```