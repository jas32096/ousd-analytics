from datetime import (
    timedelta,
    datetime,
)
from decimal import Decimal
from django.db import models

from core.logging import get_logger
import simplejson as json

log = get_logger(__name__)


class AssetBlock(models.Model):
    symbol = models.CharField(max_length=8, db_index=True)
    block_number = models.IntegerField(db_index=True)
    ora_tok_usd_min = models.DecimalField(max_digits=64, decimal_places=18, default=0)
    ora_tok_usd_max = models.DecimalField(max_digits=64, decimal_places=18, default=0)
    vault_holding = models.DecimalField(max_digits=64, decimal_places=18, default=0)
    compstrat_holding = models.DecimalField(max_digits=64, decimal_places=18, default=0)
    threepoolstrat_holding = models.DecimalField(
        max_digits=64, decimal_places=18, default=0
    )
    aavestrat_holding = models.DecimalField(max_digits=64, decimal_places=18, default=0)

    def ora_diff_basis(self):
        return (self.ora_tok_usd_max - self.ora_tok_usd_min) * Decimal(10000)

    def total(self):
        return (
            self.vault_holding
            + self.compstrat_holding
            + self.threepoolstrat_holding
            + self.aavestrat_holding
        )

    def redeem_value(self):
        return self.total() * self.redeem_price()

    def redeem_price(self):
        if self.ora_tok_usd_max > 1.0:
            return self.ora_tok_usd_max
        else:
            return Decimal(1)

    class Meta:
        indexes = [
            models.Index(fields=["block_number"]),
        ]


class DebugTx(models.Model):
    tx_hash = models.CharField(max_length=66, db_index=True)
    block_number = models.IntegerField(db_index=True)
    notes = models.TextField()
    data = models.JSONField()


class LogPointer(models.Model):
    contract = models.CharField(max_length=256, db_index=True)
    last_block = models.IntegerField(db_index=True)


class EtherscanPointer(models.Model):
    contract = models.CharField(max_length=256, db_index=True, primary_key=True)
    last_block = models.IntegerField(db_index=True)


class Log(models.Model):
    address = models.CharField(max_length=255, db_index=True)
    event_name = models.CharField(max_length=255, db_index=True, blank=True)
    topic_0 = models.CharField(max_length=255, db_index=True, blank=True)
    topic_1 = models.CharField(max_length=255, db_index=True, blank=True)
    topic_2 = models.CharField(max_length=255, db_index=True, blank=True)
    topic_3 = models.CharField(max_length=255, db_index=True, blank=True)
    data = models.TextField(max_length=256, blank=True)
    block_number = models.IntegerField(db_index=True)
    log_index = models.IntegerField(db_index=True)
    transaction_hash = models.CharField(max_length=255, db_index=True)
    transaction_index = models.IntegerField(db_index=True)
    account_balance = Decimal(0)

    def is_ousd_in(self):
        """For uniswap events"""
        return (
            self.data[2 + 3 * 64 : 2 + 4 * 64]
            != "0000000000000000000000000000000000000000000000000000000000000000"
        )

    def ousd_value(self):
        return Decimal(int(self.data, 16) / 1e18)

    class Meta:
        ordering = ["-block_number", "-log_index"]
        indexes = [
            models.Index(fields=["block_number"]),
        ]
        unique_together = ('block_number', 'transaction_index', 'log_index')


class SupplySnapshot(models.Model):
    block_number = models.IntegerField(db_index=True)
    reported_supply = models.DecimalField(max_digits=64, decimal_places=18)
    computed_supply = models.DecimalField(max_digits=64, decimal_places=18)
    non_rebasing_credits = models.DecimalField(
        max_digits=64, decimal_places=18, default=0
    )
    non_rebasing_supply = models.DecimalField(
        max_digits=64, decimal_places=18, default=0
    )
    credits = models.DecimalField(max_digits=64, decimal_places=18)
    credits_ratio = models.DecimalField(max_digits=64, decimal_places=18)
    rebasing_credits_ratio = models.DecimalField(
        max_digits=64, decimal_places=18, default=0
    )
    rebasing_credits_per_token = models.DecimalField(
        max_digits=64, decimal_places=18, default=0
    )
    apr = Decimal(0)  # Not persisted
    apy = Decimal(0)  # Not persisted
    gain = Decimal(0)  # Not persisted

    def rebasing_reported_supply(self):
        return self.reported_supply - self.non_rebasing_supply

    def rebasing_computed_supply(self):
        return self.computed_supply - self.non_rebasing_supply

    def non_rebasing_reported_supply(self):
        return self.non_rebasing_supply

    def backing_diff(self):
        return self.computed_supply - self.reported_supply

    def non_rebasing_percentage(self):
        return (self.non_rebasing_supply / self.computed_supply) * 100

    def non_rebasing_boost_percentage(self):
        return (
            (self.computed_supply / (self.computed_supply - self.non_rebasing_supply))
            - 1
        ) * 100

    def non_rebasing_boost_multiplier(self):
        return (
            (self.computed_supply / (self.computed_supply - self.non_rebasing_supply))
        )

    class Meta:
        ordering = ["-block_number"]
        indexes = [
            models.Index(fields=["block_number"]),
        ]


class OgnStakingSnapshot(models.Model):
    block_number = models.IntegerField(db_index=True, unique=True)
    ogn_balance = models.DecimalField(max_digits=64, decimal_places=18)
    total_outstanding = models.DecimalField(max_digits=64, decimal_places=18)
    user_count = models.IntegerField()


class Block(models.Model):
    block_number = models.IntegerField(primary_key=True)
    block_time = models.DateTimeField(db_index=True)


class Transaction(models.Model):
    tx_hash = models.CharField(max_length=66, primary_key=True)
    block_number = models.IntegerField(db_index=True)
    block_time = models.DateTimeField(db_index=True)
    notes = models.TextField()
    data = models.JSONField(default=dict)
    receipt_data = models.JSONField(default=dict)
    debug_data = models.JSONField(default=dict)
    internal_transactions = models.JSONField(default=dict)
    from_address = models.CharField(max_length=42, db_index=True, default='0xinvalid_address')
    to_address = models.CharField(max_length=42, db_index=True, null=True)


class OusdTransfer(models.Model):
    tx_hash = models.ForeignKey(
        "Transaction",
        to_field="tx_hash",
        on_delete=models.DO_NOTHING,
        db_index=True,
    )
    log_index = models.CharField(max_length=66, db_index=True)
    block_time = models.DateTimeField(db_index=True)
    from_address = models.CharField(max_length=42, db_index=True)
    to_address = models.CharField(max_length=42, db_index=True)
    amount = models.DecimalField(max_digits=64, decimal_places=18, default=0)


class OgnStaked(models.Model):
    tx_hash = models.CharField(max_length=66, db_index=True)
    log_index = models.CharField(max_length=66, db_index=True)
    block_time = models.DateTimeField(db_index=True)
    user_address = models.CharField(max_length=42, db_index=True)
    is_staked = models.BooleanField()
    amount = models.DecimalField(max_digits=64, decimal_places=18, default=0)
    staked_amount = models.DecimalField(max_digits=64, decimal_places=18, default=0)
    duration = models.IntegerField(default=0)
    staked_duration = models.DurationField(default=timedelta(days=0))
    rate = models.DecimalField(max_digits=64, decimal_places=18, default=0)
    stake_type = models.IntegerField(default=0)

    class Meta:
        unique_together = ('tx_hash', 'log_index')


class OracleSnapshot(models.Model):
    """ Snapshot of prices from dependency oracles """
    block_number = models.IntegerField(db_index=True)
    oracle = models.CharField(max_length=42, db_index=True)
    ticker_left = models.CharField(max_length=6, db_index=True)
    ticker_right = models.CharField(max_length=6, db_index=True)
    price = models.DecimalField(max_digits=64, decimal_places=18)


class CTokenSnapshot(models.Model):
    """ Snapshot of useful compound state for a given block """
    block_number = models.IntegerField(db_index=True)

    # Address of the cToken
    address = models.CharField(max_length=42, db_index=True)

    # These are the per-block rates in percentage (1.00 = 100%)
    borrow_rate = models.DecimalField(max_digits=64, decimal_places=18)
    supply_rate = models.DecimalField(max_digits=64, decimal_places=18)

    # These are the calculated APY in percentage (1.00 = 100%)
    borrow_apy = models.DecimalField(max_digits=64, decimal_places=18)
    supply_apy = models.DecimalField(max_digits=64, decimal_places=18)

    # Total number of cTokens in circulation
    total_supply = models.DecimalField(max_digits=64, decimal_places=18)

    # Total amount of outstanding borrows of the underlying in this market
    total_borrows = models.DecimalField(max_digits=64, decimal_places=18)

    # Total amount of reserves of the underlying held in this market
    total_reserves = models.DecimalField(max_digits=64, decimal_places=18)

    # Total known balance of this contract in terms of the underlying
    total_cash = models.DecimalField(max_digits=64, decimal_places=18)

    # The exchange rate from the underlying to the CToken
    exchange_rate_stored = models.DecimalField(
        max_digits=64,
        decimal_places=18
    )

    class Meta:
        unique_together = ('block_number', 'address')


class AnalyticsReport(models.Model):
    # A report either represents a time interval of a week or a month. For that
    # reason year property shall always be populated, with the combination of either
    # month property or week property. Months go from 1-12 and weeks go from 0-53
    # or whatever amount of weeks a certain year has

    week = models.IntegerField(null=True)
    month = models.IntegerField(null=True)
    year = models.IntegerField(db_index=True)

    # starting and ending block of the report
    block_start = models.IntegerField()
    block_end = models.IntegerField()

    # starting and ending time of the report
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    created_at = models.DateTimeField(default=datetime.now())
    updated_at = models.DateTimeField(default=datetime.now())

    # Status of the report. Valid values: processing, done
    # this is used in combination with updated_at to figure out if process making a 
    # report has failed and needs to be re-attempted
    status = models.CharField(max_length=20, default='done')

    # Contains info regarding which contracts have been called that have resulted in 
    # OUSD Swaps. (Uniswap Router, Metamask router....)
    transaction_report = models.JSONField(default=list)

    # Total number of accounts analyzed - number of accounts that have ever held OUSD
    accounts_analyzed = models.IntegerField()
    # Number of accounts holding OUSD in a given time period
    accounts_holding_ousd = models.IntegerField()
    # Number of accounts holding more than 100 OUSD in a given time period
    accounts_holding_more_than_100_ousd = models.IntegerField()
    # Number of accounts holding more than 100 OUSD after curve campaign start
    accounts_holding_more_than_100_ousd_after_curve_start = models.IntegerField(default=0)
    # Number of new accounts holding OUSD in a given time period
    new_accounts = models.IntegerField()
    # Number of new accounts after Curve campaign start
    new_accounts_after_curve_start = models.IntegerField(default=0)
    # Number of accounts that have increased their OUSD holdings ignoring rebases
    accounts_with_non_rebase_balance_increase = models.IntegerField()
    # Number of accounts that have decreased their OUSD holdings ignoring rebases
    accounts_with_non_rebase_balance_decrease = models.IntegerField()

    # Contains any info that didn't fit into other reporting stats
    report = models.JSONField(default=list)

    def __getattr__(self, name):
        if not self.report or self.report == '[]':
            return None

        report_json = json.loads(str(self.report))
        if name == 'total_supply':
            return round(report_json['supply_data']['total_supply'], 2) if 'supply_data' in report_json else None
        elif name == 'curve_metapool_total_supply':
            return report_json['curve_data']['total_supply'] if 'curve_data' in report_json else None
        elif name == 'share_earning_curve_ogn':
            return report_json['curve_data']['earning_ogn'] if 'curve_data' in report_json else None
        elif name == 'apy':
            return report_json['apy']
        elif name == 'pools':
            return report_json["supply_data"]["pools"] if "supply_data" in report_json else []
        elif name == 'other_rebasing':
            return report_json["supply_data"]["other_rebasing"] if "supply_data" in report_json else []
        elif name == 'other_non_rebasing':
            return report_json["supply_data"]["other_non_rebasing"] if "supply_data" in report_json else []


class AaveLendingPoolCoreSnapshot(models.Model):
    """ Snapshot of Aave's LendingPoolCore (v1) """

    block_number = models.IntegerField(db_index=True)

    # The underlying asset address for the reserve
    asset = models.CharField(max_length=42, db_index=True)

    # borrowingEnabled = true means users can borrow from this reserve
    borrowing_enabled = models.BooleanField()

    # The available liquidity is the balance of the core contract
    available_liquidity = models.DecimalField(max_digits=64, decimal_places=18)

    # The total liquidity is the balance of the core contract + total borrows
    total_liquidity = models.DecimalField(max_digits=64, decimal_places=18)

    # the current supply rate.
    current_liquidity_rate = models.DecimalField(
        max_digits=64,
        decimal_places=27,
    )

    # the total borrows of the reserve at a stable rate. Expressed in the
    # underlying currency
    total_borrows_stable = models.DecimalField(
        max_digits=64,
        decimal_places=18,
    )

    # the total borrows of the reserve at a variable rate. Expressed in the
    # underlying currency
    total_borrows_variable = models.DecimalField(
        max_digits=64,
        decimal_places=18,
    )

    # the current variable borrow rate
    variable_borrow_rate = models.DecimalField(
        max_digits=64,
        decimal_places=27,
    )

    # the current stable borrow rate
    stable_borrow_rate = models.DecimalField(
        max_digits=64,
        decimal_places=27,
    )

    class Meta:
        unique_together = ('block_number', 'asset')


class ThreePoolSnapshot(models.Model):
    """ Snapshot of Curve's 3Pool """

    block_number = models.IntegerField(db_index=True, unique=True)

    dai_balance = models.DecimalField(max_digits=64, decimal_places=18)
    usdc_balance = models.DecimalField(max_digits=64, decimal_places=18)
    usdt_balance = models.DecimalField(max_digits=64, decimal_places=18)

    initial_a = models.DecimalField(max_digits=64, decimal_places=18)
    future_a = models.DecimalField(max_digits=64, decimal_places=18)

    initial_a_time = models.DateTimeField()
    future_a_time = models.DateTimeField()


###############################################################################
# Monkeypatching dragons below
###############################################################################


def conditional_update(self, **kwargs):
    """ Update if the given kwargs do not match this model's prop values

    Note: This function is used as a monkeypatch method for the Django Model
    class
    """
    save = False

    for k, v in kwargs.items():
        if not hasattr(self, k):
            raise KeyError('Model does not have prop {}'.format(k))

        if getattr(self, k) != v:
            setattr(self, k, v)

            if not save:
                save = True

    if save:
        log.debug('Updating {} model data...'.format(self.__class__.__name__))
        self.save()
        return 1

    return 0


Log.add_to_class("conditional_update", conditional_update)
Transaction.add_to_class("conditional_update", conditional_update)
OusdTransfer.add_to_class("conditional_update", conditional_update)
OgnStaked.add_to_class("conditional_update", conditional_update)
