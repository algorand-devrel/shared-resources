import itertools

import pytest
from algokit_utils import (
    EnsureBalanceParameters,
    LogicError,
    TransactionParameters,
    ensure_funded,
    get_localnet_default_account,
)
from algokit_utils.beta.account_manager import AddressAndSigner
from algokit_utils.beta.algorand_client import AlgorandClient
from algokit_utils.beta.composer import AssetOptInParams
from algokit_utils.config import config
from algosdk.constants import MIN_TXN_FEE
from algosdk.util import algos_to_microalgos
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from smart_contracts.artifacts.shared_resources.shared_resources_client import (
    SharedResourcesClient,
)


@pytest.fixture(scope="session")
def shared_resources_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> SharedResourcesClient:
    """App client. Needs to have enough ALGO to own a box of ASAs."""
    config.configure(
        debug=True,
        # trace_all=True,
    )

    client = SharedResourcesClient(
        algod_client,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    client.create_bare()
    ensure_funded(
        algod_client,
        EnsureBalanceParameters(
            account_to_fund=client.app_address,
            min_spending_balance_micro_algos=algos_to_microalgos(100),
        ),
    )
    return client


@pytest.fixture(scope="session")
def bootstrapped_shared_resources(
    shared_resources_client: SharedResourcesClient,
) -> tuple[SharedResourcesClient, list[int]]:
    """
    Creating assets in the same app call is never limited by the resource count.
    Created assets are immediately available to the rest of the execution.

    The bootstrap ABI call creates 32 new assets and saves them in a Box.
    """
    sp = shared_resources_client.algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 38 * MIN_TXN_FEE
    shared_resources_client.bootstrap(
        transaction_parameters=TransactionParameters(
            suggested_params=sp, boxes=((0, b"assets"),)
        )
    )
    assets = (
        shared_resources_client.compose()
        .get_assets(
            transaction_parameters=TransactionParameters(boxes=((0, b"assets"),))
        )
        .simulate()
        .abi_results[0]
        .return_value
    )
    assert assets
    return shared_resources_client, assets


@pytest.fixture(scope="session")
def external_accounts(
    algorand_client: AlgorandClient,
    bootstrapped_shared_resources: tuple[SharedResourcesClient, list[int]],
) -> list[AddressAndSigner]:
    """External accounts that are funded and opted into the ASAs created by the app."""
    _, assets = bootstrapped_shared_resources

    accts = [algorand_client.account.random() for _ in range(4)]
    for acct in accts:
        ensure_funded(
            algorand_client.client.algod,
            EnsureBalanceParameters(
                account_to_fund=acct.address,
                min_spending_balance_micro_algos=algos_to_microalgos(50),
            ),
        )
    for acct, asset in itertools.product(accts, assets):
        algorand_client.send.asset_opt_in(
            AssetOptInParams(acct.address, asset, acct.signer)
        )

    return accts


def test_pass_access_app_account_manual_population(
    bootstrapped_shared_resources: tuple[SharedResourcesClient, list[int]],
    algod_client: AlgodClient,
) -> None:
    """
    Access the ASA balance of the app account for all ASAs.
    Dummy ABI calls to the "share_resource" method are added to increase the total group resource count.
    Each app call can access at most 8 ASAs.
    This gives the "access_balance" method access to all ASAs.

    By default, the sender's and the app's address are included as accessible foreign accounts.
    They don't decrease your resource count.

    Therefore, the app's address can be used to read the balance for all ASAs.
    """
    app_client, assets = bootstrapped_shared_resources

    sp = app_client.algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 6 * MIN_TXN_FEE
    app_client.compose().share_resource(
        transaction_parameters=TransactionParameters(foreign_assets=assets[0:8])
    ).share_resource(
        transaction_parameters=TransactionParameters(foreign_assets=assets[8:16])
    ).share_resource(
        transaction_parameters=TransactionParameters(foreign_assets=assets[16:24])
    ).share_resource(
        transaction_parameters=TransactionParameters(foreign_assets=assets[24:32])
    ).access_balance(
        addrs=[app_client.app_address],
        transaction_parameters=TransactionParameters(
            suggested_params=sp, boxes=((0, b"assets"),)
        ),
    ).execute()


def test_pass_access_external_account_manual_population(
    bootstrapped_shared_resources: tuple[SharedResourcesClient, list[int]],
    external_accounts: list[AddressAndSigner],
) -> None:
    """
    Access the ASA balance of an external account for all ASAs.
    The external account must be added explicitly as a foreign account in each dummy "resource_share" ABI call.

    Because the max resource count (for all kind of resources) in a single app call is 8, we can
     include 7 ASAs and 1 foreign account at most each app call.
    Therefore, we need one more dummy ABI call to "share_resource".
    """
    app_client, assets = bootstrapped_shared_resources
    external_acct = external_accounts[0]

    sp = app_client.algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 6 * MIN_TXN_FEE
    app_client.compose().share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[external_acct.address], foreign_assets=assets[0:7]
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[external_acct.address], foreign_assets=assets[7:14]
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[external_acct.address], foreign_assets=assets[14:21]
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[external_acct.address], foreign_assets=assets[21:28]
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[external_acct.address], foreign_assets=assets[28:32]
        )
    ).access_balance(
        addrs=[external_acct.address],
        transaction_parameters=TransactionParameters(
            suggested_params=sp, boxes=((0, b"assets"),)
        ),
    ).execute()


def test_pass_access_multiple_external_account_manual_population(
    bootstrapped_shared_resources: tuple[SharedResourcesClient, list[int]],
    external_accounts: list[AddressAndSigner],
) -> None:
    """
    Access the ASA balance of multiple external accounts for all ASAs.
    All external accounts must be added explicitly as foreign accounts in each dummy "resource_share" ABI call.

    Although the properties of an account and an ASA are available separately when added as a foreign resource,
     the asset balance is not.
    For the asset balance to be available in the entire group, the account and asset must appear
     in the same app call.
    """
    app_client, assets = bootstrapped_shared_resources

    sp = app_client.algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 6 * MIN_TXN_FEE
    app_client.compose().share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[0:4],
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[4:8],
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[8:12],
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[12:16],
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[16:20],
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[20:24],
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[24:28],
        )
    ).share_resource(
        transaction_parameters=TransactionParameters(
            accounts=[acct.address for acct in external_accounts],
            foreign_assets=assets[28:32],
        )
    ).access_balance(
        addrs=[acct.address for acct in external_accounts],
        transaction_parameters=TransactionParameters(
            suggested_params=sp, boxes=((0, b"assets"),)
        ),
    ).execute()


def test_pass_access_multiple_external_account_auto_population(
    bootstrapped_shared_resources: tuple[SharedResourcesClient, list[int]],
    external_accounts: list[AddressAndSigner],
) -> None:
    """
    Access the ASA balance of multiple external accounts for all ASAs.

    Resource population can handle this for you
     (if enough app calls are present in the group to add the needed resources).
    """
    # FIXME: Add an example when resource population is added to Python utils.


def test_fail_access_external_account_manual_population(
    bootstrapped_shared_resources: tuple[SharedResourcesClient, list[int]],
    external_accounts: list[AddressAndSigner],
) -> None:
    """
    Fail case for accessing an ASA balance.
    Both the ASA and the account appear at least once in the group.
    Their individual properties are available.

    However, since they don't appear together in the first app call we expect the related ASA balance
     to not be available.
    """
    app_client, assets = bootstrapped_shared_resources
    external_acct = external_accounts[0]

    sp = app_client.algod_client.suggested_params()
    sp.flat_fee = True
    sp.fee = 6 * MIN_TXN_FEE
    with pytest.raises(LogicError, match="unavailable Holding"):
        app_client.compose().share_resource(
            transaction_parameters=TransactionParameters(foreign_assets=assets[0:7])
        ).share_resource(
            transaction_parameters=TransactionParameters(
                accounts=[external_acct.address], foreign_assets=assets[7:14]
            )
        ).share_resource(
            transaction_parameters=TransactionParameters(
                accounts=[external_acct.address], foreign_assets=assets[14:21]
            )
        ).share_resource(
            transaction_parameters=TransactionParameters(
                accounts=[external_acct.address], foreign_assets=assets[21:28]
            )
        ).share_resource(
            transaction_parameters=TransactionParameters(
                accounts=[external_acct.address], foreign_assets=assets[28:32]
            )
        ).access_balance(
            addrs=[external_acct.address],
            transaction_parameters=TransactionParameters(
                suggested_params=sp, boxes=((0, b"assets"),)
            ),
        ).execute()
