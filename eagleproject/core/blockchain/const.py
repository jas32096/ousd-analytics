from decimal import Decimal

from core.addresses import (
    COMP,
    COMPENSATION_CLAIMS,
    COMPOUND_GOVERNOR_ALPHA,
    COMPOUND_TIMELOCK,
    CDAI,
    CUSDC,
    CUSDT,
    DAI,
    GOVERNOR,
    OGN_STAKING,
    OUSD,
    OUSD_USDT_UNISWAP,
    STRATAAVEDAI,
    STRATCOMP,
    TIMELOCK,
    USDT,
    USDC,
    VAULT,
)

START_OF_EVERYTHING = 10884500

CONTRACT_FOR_SYMBOL = {
    "DAI": DAI,
    "USDT": USDT,
    "USDC": USDC,
    "COMP": COMP,
}
SYMBOL_FOR_CONTRACT = {v: k for (k, v) in CONTRACT_FOR_SYMBOL.items()}

DECIMALS_FOR_SYMBOL = {
    "COMP": 18,
    "DAI": 18,
    "USDT": 6,
    "USDC": 6,
}

THREEPOOLINDEX_FOR_ASSET = {
    DAI: 0,
    USDC: 1,
    USDT: 2,
}

COMPOUND_FOR_SYMBOL = {
    "DAI": CDAI,
    "USDT": CUSDT,
    "USDC": CUSDC,
}

LOG_CONTRACTS = [
    GOVERNOR,
    OUSD,
    VAULT,
    STRATCOMP,
    STRATAAVEDAI,
    OUSD_USDT_UNISWAP,
    TIMELOCK,
    OGN_STAKING,
    COMPOUND_GOVERNOR_ALPHA,
    COMPOUND_TIMELOCK,
    COMPENSATION_CLAIMS,
]
ETHERSCAN_CONTRACTS = [GOVERNOR, OUSD, VAULT, TIMELOCK]

ASSET_TICKERS = ["DAI", "USDC", "USDT"]

BLOCKS_PER_MINUTE = 4
BLOCKS_PER_HOUR = BLOCKS_PER_MINUTE * 60
BLOCKS_PER_DAY = BLOCKS_PER_HOUR * 24
BLOCKS_PER_YEAR = BLOCKS_PER_DAY * 365

E_6 = Decimal(1e6)
E_8 = Decimal(1e8)
E_18 = Decimal(1e18)
