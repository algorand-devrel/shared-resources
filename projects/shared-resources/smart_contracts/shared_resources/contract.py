from algopy import ARC4Contract, Asset, Box, arc4, ensure_budget, itxn, urange


class SharedResources(ARC4Contract):
    def __init__(self) -> None:
        self.assets = Box(arc4.DynamicArray[arc4.UInt64])

    @arc4.abimethod
    def bootstrap(self) -> None:
        assert not self.assets, "App was already bootstrapped"
        self.assets.value = arc4.DynamicArray[arc4.UInt64]()

        # Creating 32 assets and adding their IDs to the array costs opcode budget.
        # Each app call in the group gives 700 opcode budget.
        # We need 5 extra app call in the group that are going to add opcode budget to this method call.
        # AlgoPy provides this simple function call that will ensure enough opcode budget is available.
        ensure_budget(5 * 700)
        for i in urange(32):  # noqa: B007
            new_asa = itxn.AssetConfig(total=10, decimals=0).submit()
            self.assets.value.append(arc4.UInt64(new_asa.created_asset.id))

    @arc4.abimethod
    def access_balance(self, addrs: arc4.DynamicArray[arc4.Address]) -> None:
        ensure_budget(5 * 700)
        for addr in addrs:
            for asset_id in self.assets.value:
                Asset(asset_id.native).balance(addr.native)

    @arc4.abimethod
    def share_resource(self) -> None:
        pass

    @arc4.abimethod(readonly=True)
    def get_assets(self) -> arc4.DynamicArray[arc4.UInt64]:
        return self.assets.value
