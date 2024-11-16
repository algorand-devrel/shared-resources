# Atomic Group Resource Sharing

## Introduction
An Atomic Transaction Group is an Algorand Layer-1 feature that allows multiple actions to take place in an
all-or-none fashion.

In addition, resources referenced by transactions in a group are also available to the rest of the group.
This mechanism can be used to bypass single-app-call limitations of resource count.

# Examples
This [integration test](./projects/shared-resources/tests/shared_resources_integration_test.py) exemplifies some use cases of resource sharing in an atomic group.
The [example app](./projects/shared-resources/smart_contracts/shared_resources/contract.py) creates 32 ASAs after creation with the `bootstrap` method and saves the IDs a box.
After that, the `access_balance` method can be called with a list of accounts as argument.
This method will try to read ASA balance for all argument accounts.

If only one account is passed, the app will make 32 balance accesses. If two accounts are passed, the app will make 64 balance accesses (and so on).

Normally a resource is available to the entire group if it is references anywhere in the group.
For account's ASA balances, both the account and the asset need to appear in the same transaction anywhere in the group.
They are added by calling the same application on its (dummy) method `share_resource`.

# Using Lora
Users are encouraged to use [Lora](https://lora.algokit.io/), its App Lab, and Transaction Wizard to manually construct an atomic group
that replicates the examples.
You can also use automatic resource population after adding empty app calls to the group and let it figure out which resources are needed.
