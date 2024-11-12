from algopy import ARC4Contract, Asset, Box, arc4, ensure_budget, itxn, urange


class SharedResources(ARC4Contract):
    def __init__(self) -> None:
        self.assets = Box(arc4.DynamicArray[arc4.UInt64])

    @arc4.abimethod
    def bootstrap(self) -> None:
        assert not self.assets, "App was already bootstrapped"
        self.assets.value = arc4.DynamicArray[arc4.UInt64]()

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
