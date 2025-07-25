"""Test fork covariant markers and their effect on test parametrization."""

import pytest


@pytest.mark.parametrize(
    "test_function,outcomes,error_string",
    [
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types()
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                pass
            """,
            {"passed": 3, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_tx_types",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(selector=lambda tx_type: tx_type != 0)
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                pass
            """,
            {"passed": 2, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_tx_types_with_selector",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(
                marks=lambda tx_type: pytest.mark.skip("incompatible") if tx_type == 1 else None,
            )
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                assert tx_type != 1
            """,
            {"passed": 2, "xpassed": 0, "failed": 0, "skipped": 1, "errors": 0},
            None,
            id="with_all_tx_types_with_marks_lambda",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(marks=pytest.mark.skip("incompatible"))
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                assert False
            """,
            {"passed": 0, "xpassed": 0, "failed": 0, "skipped": 3, "errors": 0},
            None,
            id="with_all_tx_types_with_marks_lambda",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(marks=[pytest.mark.skip("incompatible")])
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                assert False
            """,
            {"passed": 0, "xpassed": 0, "failed": 0, "skipped": 3, "errors": 0},
            None,
            id="with_all_tx_types_with_marks_lambda",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(
                marks=(
                    lambda tx_type:
                        [pytest.mark.xfail, pytest.mark.slow]
                        if tx_type == 1 else None
                    ),
            )
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(request, state_test, tx_type):
                mark_names = [mark.name for mark in request.node.iter_markers()]

                assert "state_test" in mark_names
                if tx_type == 1:
                    assert "slow" in mark_names
            """,
            {"passed": 2, "xpassed": 1, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_tx_types_with_marks_lambda_multiple_marks",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_contract_creating_tx_types()
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                pass
            """,
            {"passed": 3, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_contract_creating_tx_types",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_contract_creating_tx_types()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                pass
            """,
            {"passed": 3, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_contract_creating_tx_types",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_precompiles()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, precompile):
                pass
            """,
            {"passed": 10, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_precompiles",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_evm_code_types()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, evm_code_type):
                pass
            """,
            {"passed": 1, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_evm_code_types",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_call_opcodes()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, call_opcode):
                pass
            """,
            {"passed": 4, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_call_opcodes",
        ),
        pytest.param(
            """
            import pytest
            from ethereum_test_tools import EVMCodeType
            @pytest.mark.with_all_call_opcodes(
                selector=(lambda _, evm_code_type: evm_code_type == EVMCodeType.LEGACY)
            )
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, call_opcode):
                pass
            """,
            {"passed": 4, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_call_opcodes_with_selector_for_evm_code_type",
        ),
        pytest.param(
            """
            import pytest
            from ethereum_test_tools import Opcodes as Op
            @pytest.mark.with_all_call_opcodes(selector=lambda call_opcode: call_opcode == Op.CALL)
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, call_opcode):
                pass
            """,
            {"passed": 1, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_call_opcodes_with_selector",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_create_opcodes()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, create_opcode):
                pass
            """,
            {"passed": 2, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_create_opcodes",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_call_opcodes()
            @pytest.mark.with_all_precompiles()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, call_opcode, precompile):
                pass
            """,
            {"passed": 4 * 10, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_call_opcodes_and_precompiles",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_call_opcodes()
            @pytest.mark.with_all_create_opcodes()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, call_opcode, create_opcode):
                pass
            """,
            {"passed": 2 * 4, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_call_opcodes_and_create_opcodes",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_system_contracts()
            @pytest.mark.valid_from("Cancun")
            @pytest.mark.valid_until("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, system_contract):
                pass
            """,
            {"passed": 1, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_system_contracts",
        ),
        pytest.param(
            """
            import pytest
            from ethereum_test_tools import Transaction
            @pytest.mark.with_all_typed_transactions
            @pytest.mark.valid_from("Berlin")
            @pytest.mark.valid_until("Berlin")
            @pytest.mark.state_test_only
            def test_case(state_test, typed_transaction):
                assert isinstance(typed_transaction, Transaction)
                assert typed_transaction.ty in [0, 1]  # Berlin supports types 0 and 1
            """,
            {"passed": 2, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_typed_transactions_berlin",
        ),
        pytest.param(
            """
            import pytest
            from ethereum_test_tools import Transaction
            @pytest.mark.with_all_typed_transactions()
            @pytest.mark.valid_from("London")
            @pytest.mark.valid_until("London")
            @pytest.mark.state_test_only
            def test_case(state_test, typed_transaction, pre):
                assert isinstance(typed_transaction, Transaction)
                assert typed_transaction.ty in [0, 1, 2]  # London supports types 0, 1, 2
            """,
            {"passed": 3, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_typed_transactions_london",
        ),
        pytest.param(
            """
            import pytest
            from ethereum_test_tools import Transaction
            from ethereum_test_base_types import AccessList

            # Override the type 3 transaction fixture
            @pytest.fixture
            def type_3_default_transaction(pre):
                sender = pre.fund_eoa()

                return Transaction(
                    ty=3,
                    sender=sender,
                    max_fee_per_gas=10**10,
                    max_priority_fee_per_gas=10**9,
                    max_fee_per_blob_gas=10**8,
                    gas_limit=300_000,
                    data=b"\\xFF" * 50,
                    access_list=[
                        AccessList(address=0x1111, storage_keys=[10, 20]),
                    ],
                    blob_versioned_hashes=[
                        0x0111111111111111111111111111111111111111111111111111111111111111,
                    ],
                )

            @pytest.mark.with_all_typed_transactions()
            @pytest.mark.valid_at("Cancun")
            @pytest.mark.state_test_only
            def test_case(state_test, typed_transaction, pre):
                assert isinstance(typed_transaction, Transaction)
                if typed_transaction.ty == 3:
                    # Verify our override worked
                    assert typed_transaction.data == b"\\xFF" * 50
                    assert len(typed_transaction.blob_versioned_hashes) == 1
            """,
            {"passed": 4, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="with_all_typed_transactions_with_override",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(invalid_parameter="invalid")
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                pass
            """,
            {"passed": 0, "failed": 0, "skipped": 0, "errors": 1},
            "Unknown arguments to with_all_tx_types",
            id="invalid_covariant_marker_parameter",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(selector=None)
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                pass
            """,
            {"passed": 0, "failed": 0, "skipped": 0, "errors": 1},
            "selector must be a function",
            id="invalid_selector",
        ),
        pytest.param(
            """
            import pytest
            @pytest.mark.with_all_tx_types(lambda tx_type: tx_type != 0)
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Paris")
            @pytest.mark.state_test_only
            def test_case(state_test, tx_type):
                pass
            """,
            {"passed": 0, "failed": 0, "skipped": 0, "errors": 1},
            "Only keyword arguments are supported",
            id="selector_as_positional_argument",
        ),
        pytest.param(
            """
            import pytest

            def covariant_function(fork):
                return [1, 2] if fork.name() == "Paris" else [3, 4, 5]

            @pytest.mark.parametrize_by_fork(
                argnames=["test_parameter"],
                fn=covariant_function,
            )
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Shanghai")
            @pytest.mark.state_test_only
            def test_case(state_test, test_parameter):
                pass
            """,
            {"passed": 5, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="custom_covariant_marker",
        ),
        pytest.param(
            """
            import pytest

            def covariant_function(fork):
                return [[1, 2], [3, 4]] if fork.name() == "Paris" else [[4, 5], [5, 6], [6, 7]]

            @pytest.mark.parametrize_by_fork("test_parameter,test_parameter_2", covariant_function)
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Shanghai")
            @pytest.mark.state_test_only
            def test_case(state_test, test_parameter, test_parameter_2):
                pass
            """,
            {"passed": 5, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="multi_parameter_custom_covariant_marker",
        ),
        pytest.param(
            """
            import pytest

            def covariant_function(fork):
                return [
                    pytest.param(1, id="first_value"),
                    2,
                ] if fork.name() == "Paris" else [
                    pytest.param(3, id="third_value"),
                    4,
                    5,
                ]

            @pytest.mark.parametrize_by_fork("test_parameter",covariant_function)
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Shanghai")
            @pytest.mark.state_test_only
            def test_case(state_test, test_parameter):
                pass
            """,
            {"passed": 5, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="custom_covariant_marker_pytest_param_id",
        ),
        pytest.param(
            """
            import pytest

            def covariant_function(fork):
                return [
                    pytest.param(1, 2, id="first_test"),
                    pytest.param(3, 4, id="second_test"),
                ] if fork.name() == "Paris" else [
                    pytest.param(4, 5, id="fourth_test"),
                    pytest.param(5, 6, id="fifth_test"),
                    pytest.param(6, 7, id="sixth_test"),
                ]

            @pytest.mark.parametrize_by_fork(argnames=[
                "test_parameter", "test_parameter_2"
            ], fn=covariant_function)
            @pytest.mark.valid_from("Paris")
            @pytest.mark.valid_until("Shanghai")
            @pytest.mark.state_test_only
            def test_case(state_test, test_parameter, test_parameter_2):
                pass
            """,
            {"passed": 5, "failed": 0, "skipped": 0, "errors": 0},
            None,
            id="multi_parameter_custom_covariant_marker_pytest_param_id",
        ),
    ],
)
def test_fork_covariant_markers(
    pytester, test_function: str, outcomes: dict, error_string: str | None
):
    """
    Test fork covariant markers in an isolated test session, i.e., in
    a `fill` execution.

    In the case of an error, check that the expected error string is in the
    console output.
    """
    pytester.makepyfile(test_function)
    pytester.copy_example(name="src/cli/pytest_commands/pytest_ini_files/pytest-fill.ini")
    result = pytester.runpytest("-c", "pytest-fill.ini")
    result.assert_outcomes(**outcomes)
    if outcomes["errors"]:
        assert error_string is not None
        assert error_string in "\n".join(result.stdout.lines)
