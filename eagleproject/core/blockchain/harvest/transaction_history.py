from decimal import *
from django import db
from operator import attrgetter
from multiprocessing import (
    Process,
    Manager,
)

from core.models import (
    Log,
    OusdTransfer,
    Block,
    Transaction,
    AnalyticsReport
)

from core.blockchain.sigs import (
    TRANSFER,
)

from django.db.models import Q
from core.blockchain.harvest.transactions import (
    explode_log_data
)
from core.blockchain.rpc import (
    creditsBalanceOf,
)
from core.blockchain.rpc import (
    balanceOf,
    totalSupply
)
from core.blockchain.apy import (
    get_trailing_apy,
)
from datetime import (
    datetime,
)

from core.blockchain.const import (
    START_OF_EVERYTHING_TIME,
    report_stats,
    curve_report_stats,
    E_18,
    START_OF_CURVE_CAMPAIGN_TIME,
    START_OF_OUSD_V2
)

from core.blockchain.utils import (
    chunks,
)
from core.blockchain.harvest.snapshots import (
    ensure_supply_snapshot,
    calculate_snapshot_data
)

import calendar

from core.channels.email import (
    Email
)
from django.template.loader import render_to_string
from django.conf import settings
from core.blockchain.decode import slot
from core.blockchain.addresses import (
    CONTRACT_ADDR_TO_NAME,
    CURVE_METAPOOL,
    CURVE_METAPOOL_GAUGE,
)

import simplejson as json

ACCOUNT_ANALYZE_PARALLELISM=30

class rebase_log:
    # block_number
    # credits_per_token
    # balance

    def __init__(self, block_number, credits_per_token, tx_hash):
        self.block_number = block_number
        self.credits_per_token = credits_per_token
        self.tx_hash = tx_hash

    def set_block_time(self, block_time):
        self.block_time = block_time

    def __str__(self):
        return 'rebase log: block: {} creditsPerToken: {} balance: {} block_time:{}'.format(self.block_number, self.credits_per_token, self.balance if hasattr(self, 'balance') else 0, self.block_time if hasattr(self, 'block_time') else False)

class transfer_log:
    # block_number
    # amount
    # credits_per_token
    # balance

    def __init__(self, block_number, tx_hash, amount, from_address, to_address, block_time, log_index):
        self.block_number = block_number
        self.tx_hash = tx_hash
        self.amount = amount
        self.from_address = from_address
        self.to_address = to_address
        self.block_time = block_time
        self.log_index = log_index

    def __str__(self):
        return 'transfer log: block: {} amount: {} tx_hash: {} creditsPerToken: {} balance: {}'.format(self.block_number, self.amount, self.tx_hash, self.credits_per_token if hasattr(self, 'credits_per_token') else 'N/A', self.balance if hasattr(self, 'balance') else 'N/A')

class address_analytics:
    # OUSD increasing/decreasing is ignoring rebase events
    def __init__(self, is_holding_ousd, is_holding_more_than_100_ousd, is_new_account, has_ousd_increased, has_ousd_decreased, is_new_after_curve_start, new_after_curve_and_hold_more_than_100):
        self.is_holding_ousd = is_holding_ousd
        self.is_holding_more_than_100_ousd = is_holding_more_than_100_ousd
        self.is_new_account = is_new_account
        self.has_ousd_increased = has_ousd_increased
        self.has_ousd_decreased = has_ousd_decreased
        self.is_new_after_curve_start = is_new_after_curve_start
        self.new_after_curve_and_hold_more_than_100 = new_after_curve_and_hold_more_than_100

    def __str__(self):
        return 'address_analytics: is_holding_ousd: {self.is_holding_ousd} is_holding_more_than_100_ousd: {self.is_holding_more_than_100_ousd} is_new_account: {self.is_new_account} has_ousd_increased: {self.has_ousd_increased} has_ousd_decreased: {self.has_ousd_decreased} is_new_after_curve_start: {self.is_new_after_curve_start} new_after_curve_and_hold_more_than_100: {self.new_after_curve_and_hold_more_than_100}'.format(self=self)


class analytics_report:
    def __init__(
        self,
        accounts_analyzed,
        accounts_holding_ousd,
        accounts_holding_more_than_100_ousd,
        accounts_holding_more_than_100_ousd_after_curve_start,
        new_accounts,
        new_accounts_after_curve_start,
        accounts_with_non_rebase_balance_increase,
        accounts_with_non_rebase_balance_decrease,
        supply_data,
        apy,
        curve_data
    ):
        self.accounts_analyzed = accounts_analyzed
        self.accounts_holding_ousd = accounts_holding_ousd
        self.accounts_holding_more_than_100_ousd = accounts_holding_more_than_100_ousd
        self.accounts_holding_more_than_100_ousd_after_curve_start = accounts_holding_more_than_100_ousd_after_curve_start
        self.new_accounts = new_accounts
        self.new_accounts_after_curve_start = new_accounts_after_curve_start
        self.accounts_with_non_rebase_balance_increase = accounts_with_non_rebase_balance_increase
        self.accounts_with_non_rebase_balance_decrease = accounts_with_non_rebase_balance_decrease
        self.supply_data = supply_data
        self.apy = apy
        self.curve_data = curve_data

    def __str__(self):
        return 'Analytics report: accounts_analyzed: {} accounts_holding_ousd: {} accounts_holding_more_than_100_ousd: {} accounts_holding_more_than_100_ousd_after_curve_start: {} new_accounts: {} new_accounts_after_curve_start: {} accounts_with_non_rebase_balance_increase: {} accounts_with_non_rebase_balance_decrease: {} apy: {} supply_data: {} curve_data: {}'.format(self.accounts_analyzed, self.accounts_holding_ousd, self.accounts_holding_more_than_100_ousd, self.accounts_holding_more_than_100_ousd_after_curve_start, self.new_accounts, self.new_accounts_after_curve_start, self.accounts_with_non_rebase_balance_increase, self.accounts_with_non_rebase_balance_decrease, self.apy, self.supply_data, self.curve_data)

class transaction_analysis:
    def __init__(
        self,
        account,
        tx_hash,
        contract_address,
        internal_transactions,
        received_eth,
        sent_eth,
        transfer_ousd_out,
        transfer_ousd_in,
        transfer_coin_out,
        transfer_coin_in,
        ousd_transfer_from,
        ousd_transfer_to,
        ousd_transfer_amount,
        transfer_log_count,
        classification
    ):
        self.account = account
        self.tx_hash = tx_hash
        self.contract_address = contract_address
        self.internal_transactions = internal_transactions
        self.received_eth = received_eth
        self.sent_eth = sent_eth
        self.transfer_ousd_out = transfer_ousd_out
        self.transfer_ousd_in = transfer_ousd_in
        self.transfer_coin_out = transfer_coin_out
        self.transfer_coin_in = transfer_coin_in
        self.ousd_transfer_from = ousd_transfer_from
        self.ousd_transfer_to = ousd_transfer_to
        self.ousd_transfer_amount = ousd_transfer_amount
        self.transfer_log_count = transfer_log_count
        self.classification = classification

    def __str__(self):
        return 'transaction analysis: account: {} tx_hash: {} classification: {} contract_address: {} received_eth: {} sent_eth: {} transfer_ousd_out: {} transfer_ousd_in: {} transfer_coin_out {} transfer_coin_in {} ousd_transfer_from {} ousd_transfer_to {} ousd_transfer_amount {} transfer_log_count {}'.format(
            self.account,
            self.tx_hash,
            self.classification,
            self.contract_address,
            self.received_eth,
            self.sent_eth,
            self.transfer_ousd_out,
            self.transfer_ousd_in,
            self.transfer_coin_out,
            self.transfer_coin_in,
            self.ousd_transfer_from,
            self.ousd_transfer_to,
            self.ousd_transfer_amount,
            self.transfer_log_count
        )


# get first available block from the given time.
# Ascending=True -> closest youngest block
# Ascending=False -> closest oldest block
def get_block_number_from_block_time(time, ascending = False):
    if ascending :
        result = Block.objects.filter(block_time__gte=time).order_by('block_time')[:1]
    else:
        result = Block.objects.filter(block_time__lte=time).order_by('-block_time')[:1]

    if len(result) != 1:
        raise Exception('Can not find block time {} than {}'.format('younger' if ascending else 'older', str(time)))
    return result[0].block_number

def calculate_report_change(current_report, previous_report):
    changes = {
        "total_supply": 0,
        "apy": 0,
        "accounts_analyzed": 0,
        "accounts_holding_ousd": 0,
        "accounts_holding_more_than_100_ousd": 0,
        "accounts_holding_more_than_100_ousd_after_curve_start": 0,
        "new_accounts": 0,
        "new_accounts_after_curve_start": 0,
        "accounts_with_non_rebase_balance_increase": 0,
        "accounts_with_non_rebase_balance_decrease": 0,
        "other_rebasing": 0,
        "other_non_rebasing": 0,
        "curve_metapool_total_supply": 0,
        "share_earning_curve_ogn": 0,
    }

    def calculate_difference(current_stat, previous_stat):
        if previous_stat == 0 or previous_stat is None:
            return 0

        return (current_stat - previous_stat) / previous_stat * 100

    if previous_report is None:
        return changes

    json_report = json.loads(str(current_report.report))
    json_report_previous = json.loads(str(previous_report.report))

    supply_data = json_report["supply_data"] if "supply_data" in json_report else None
    supply_data_previous = json_report_previous["supply_data"] if "supply_data" in json_report_previous else None

    curve_data = json_report["curve_data"] if "curve_data" in json_report else None
    curve_data_previous = json_report_previous["curve_data"] if "curve_data" in json_report_previous else None

    changes['total_supply'] = calculate_difference(current_report.total_supply, previous_report.total_supply)
    changes['apy'] = calculate_difference(current_report.apy, previous_report.apy)
    changes['accounts_analyzed'] = calculate_difference(current_report.accounts_analyzed, previous_report.accounts_analyzed)
    changes['accounts_holding_ousd'] = calculate_difference(current_report.accounts_holding_ousd, previous_report.accounts_holding_ousd)
    changes['accounts_holding_more_than_100_ousd'] = calculate_difference(current_report.accounts_holding_more_than_100_ousd, previous_report.accounts_holding_more_than_100_ousd)
    changes['accounts_holding_more_than_100_ousd_after_curve_start'] = calculate_difference(current_report.accounts_holding_more_than_100_ousd_after_curve_start, previous_report.accounts_holding_more_than_100_ousd_after_curve_start)
    changes['new_accounts'] = calculate_difference(current_report.new_accounts, previous_report.new_accounts)
    changes['new_accounts_after_curve_start'] = calculate_difference(current_report.new_accounts_after_curve_start, previous_report.new_accounts_after_curve_start)
    changes['accounts_with_non_rebase_balance_increase'] = calculate_difference(current_report.accounts_with_non_rebase_balance_increase, previous_report.accounts_with_non_rebase_balance_increase)
    changes['accounts_with_non_rebase_balance_decrease'] = calculate_difference(current_report.accounts_with_non_rebase_balance_decrease, previous_report.accounts_with_non_rebase_balance_decrease)
    if supply_data is not None and supply_data_previous is not None:
        changes['other_rebasing'] = calculate_difference(supply_data['other_rebasing'], supply_data_previous['other_rebasing'])
        changes['other_non_rebasing'] = calculate_difference(supply_data['other_non_rebasing'], supply_data_previous['other_non_rebasing'])

    if curve_data is not None and curve_data_previous is not None:
        changes['curve_metapool_total_supply'] = calculate_difference(current_report.curve_metapool_total_supply, previous_report.curve_metapool_total_supply)
        changes['share_earning_curve_ogn'] = calculate_difference(current_report.share_earning_curve_ogn, previous_report.share_earning_curve_ogn)


    return changes

def upsert_report(week_option, month_option, year, status, report, block_start_number, block_end_number, start_time, end_time, do_only_transaction_analytics, transaction_report):
    analyticsReport = None

    params = {
        "block_start": block_start_number,
        "block_end": block_end_number,
        "start_time": start_time,
        "end_time": end_time,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "status": status,
        "accounts_analyzed": report.accounts_analyzed if report is not None else 0,
        "accounts_holding_ousd": report.accounts_holding_ousd if report is not None else 0,
        "accounts_holding_more_than_100_ousd": report.accounts_holding_more_than_100_ousd if report is not None else 0,
        "accounts_holding_more_than_100_ousd_after_curve_start": report.accounts_holding_more_than_100_ousd_after_curve_start if report is not None else 0,
        "new_accounts": report.new_accounts if report is not None else 0,
        "new_accounts_after_curve_start": report.new_accounts_after_curve_start if report is not None else 0,
        "accounts_with_non_rebase_balance_increase": report.accounts_with_non_rebase_balance_increase if report is not None else 0,
        "accounts_with_non_rebase_balance_decrease": report.accounts_with_non_rebase_balance_decrease if report is not None else 0,
        "transaction_report": transaction_report,
        "report": json.dumps(report.__dict__) if report is not None else '[]'
    }

    if do_only_transaction_analytics:
        if week_option != None:
            analyticsReport = AnalyticsReport.objects.get(
                week=week_option,
                year=year
            )
        else:
            analyticsReport = AnalyticsReport.objects.get(
                month=month_option,
                year=year
            )

        if analyticsReport is None:
            raise Exception('Report not found week: {} month: {} year: {}'.format(week_option, month_option, year))

        analyticsReport.transaction_report = transaction_report
        analyticsReport.save()
    else:
        if week_option != None:
            analyticsReport, created = AnalyticsReport.objects.get_or_create(
                week=week_option,
                year=year,
                defaults=params,
            )
        else:
            analyticsReport, created = AnalyticsReport.objects.get_or_create(
                month=month_option,
                year=year,
                defaults=params,
            )

        if not created:
            for key in params.keys():
                if key == 'created_at':
                    continue

                setattr(analyticsReport, key, params.get(key))
            analyticsReport.save()

    return analyticsReport

def create_time_interval_report_for_previous_week(week_override, do_only_transaction_analytics = False):
    year_number = datetime.now().year
    # number of the week in a year - for the previous week
    week_number = week_override if week_override is not None else int(datetime.now().strftime("%W")) - 1

    if week_override is None and not should_create_new_report(year_number, None, week_number):
        print("Report for year: {} and week: {} does not need creation".format(year_number, week_number))
        return 

    # TODO: this will work incorrectly when the week falls on new year
    week_interval = "{year}-W{week}".format(year = year_number, week=week_number)

    # Monday of selected week
    start_time = datetime.strptime(week_interval + '-1', "%Y-W%W-%w")
    # Sunday of selected week
    end_time = datetime.strptime(week_interval + '-0', "%Y-W%W-%w").replace(hour=23, minute=59, second=59)

    block_start_number = get_block_number_from_block_time(start_time, True)
    block_end_number = get_block_number_from_block_time(end_time, False)

    transaction_report = do_transaction_analytics(block_start_number, block_end_number, start_time, end_time)

    upsert_report(
        week_number,
        None,
        year_number,
        "processing",
        None,
        block_start_number, 
        block_end_number,
        start_time,
        end_time,
        do_only_transaction_analytics,
        transaction_report
    )

    # don't do the general report if not needed
    if do_only_transaction_analytics:
        return

    report = create_time_interval_report(
        block_start_number,
        block_end_number,
        start_time,
        end_time
    )

    db_report = upsert_report(
        week_number,
        None,
        year_number,
        "done",
        report,
        block_start_number, 
        block_end_number,
        start_time,
        end_time,
        do_only_transaction_analytics,
        transaction_report
    )

    # if it is a cron job report
    if week_override is None:
        # if first week of the year report
        if (week_number == 0):
            week_number = 53
            year_number -= 1
        else :
            week_number -= 1

        week_before_report = AnalyticsReport.objects.filter(Q(year=year_number) & Q(week=week_number))
        preb_db_report = week_before_report[0] if len(week_before_report) != 0 else None
        send_report_email('Weekly report', db_report, preb_db_report, "Weekly")

def should_create_new_report(year, month_option, week_option):
    if month_option is not None: 
        existing_report = AnalyticsReport.objects.filter(Q(year=year) & Q(month=month_option))
    elif week_option is not None: 
        existing_report = AnalyticsReport.objects.filter(Q(year=year) & Q(week=week_option))

    if len(existing_report) == 1:
        existing_report = existing_report[0]

        # nothing to do here, report is already done
        if existing_report.status == 'done':
            return False

        # in seconds
        report_age = (datetime.now() - existing_report.updated_at.replace(tzinfo=None)).total_seconds()

        # report might still be processing
        if report_age < 3 * 60 * 60:
            return False

    return True

def create_time_interval_report_for_previous_month(month_override, do_only_transaction_analytics = False):
    # number of the month in a year - for the previous month
    month_number = month_override if month_override is not None else int(datetime.now().strftime("%m")) - 1
    year_number = datetime.now().year + (-1 if month_number == 12 else 0)

    if month_override is None and not should_create_new_report(year_number, month_number, None):
        print("Report for year: {} and month: {} does not need creation".format(year_number, month_number))
        return 

    month_interval = "{year}-m{month}".format(year=year_number, month=month_number)

    (start_day, end_day) = calendar.monthrange(year_number, month_number)

    # Monday of selected week
    start_time = datetime.strptime(month_interval + '-1', "%Y-m%m-%d")
    # Sunday of selected week
    end_time = datetime.strptime(month_interval + '-{}'.format(end_day), "%Y-m%m-%d").replace(hour=23, minute=59, second=59)

    block_start_number = get_block_number_from_block_time(start_time, True)
    block_end_number = get_block_number_from_block_time(end_time, False)

    transaction_report = do_transaction_analytics(block_start_number, block_end_number, start_time, end_time)

    upsert_report(
        None,
        month_number,
        year_number,
        "processing",
        None,
        block_start_number, 
        block_end_number,
        start_time,
        end_time,
        do_only_transaction_analytics,
        transaction_report
    )

    # don't do the general report if not needed
    if do_only_transaction_analytics:
        return

    report = create_time_interval_report(
        block_start_number,
        block_end_number,
        start_time,
        end_time
    )

    db_report = upsert_report(
        None,
        month_number,
        year_number,
        "done",
        report,
        block_start_number, 
        block_end_number,
        start_time,
        end_time,
        do_only_transaction_analytics,
        transaction_report
    )

    # if it is a cron job report
    if month_override is None:
        # if first month of the year report
        if (month_number == 1):
            month_number = 12
            year_number -= 1
        else :
            month_number -= 1

        month_before_report = AnalyticsReport.objects.filter(Q(year=year_number) & Q(month=month_number))
        preb_db_report = month_before_report[0] if len(month_before_report) != 0 else None
        send_report_email('Monthly report', db_report, preb_db_report, "Monthly")

# get all accounts that at some point held OUSD
def fetch_all_holders():
    to_addresses = list(map(lambda log: log['to_address'], OusdTransfer.objects.values('to_address').distinct()))
    from_addresses = list(map(lambda log: log['from_address'], OusdTransfer.objects.values('from_address').distinct()))
    return list(set(filter(lambda address: address not in ['0x0000000000000000000000000000000000000000', '0x000000000000000000000000000000000000dead'], to_addresses + from_addresses)))

def fetch_supply_data(block_number):
    ensure_supply_snapshot(block_number)
    [pools, totals_by_rebasing, other_rebasing, other_non_rebasing, snapshot] = calculate_snapshot_data(block_number)

    return {
        'total_supply': snapshot.reported_supply,
        'pools': pools,
        'totals_by_rebasing': totals_by_rebasing,
        'other_rebasing': other_rebasing,
        'other_non_rebasing': other_non_rebasing,
    }

def get_curve_data(to_block):
    balance = balanceOf(CURVE_METAPOOL, CURVE_METAPOOL_GAUGE, 18, to_block)
    supply = totalSupply(CURVE_METAPOOL, 18, to_block)
    return {
        "total_supply": supply,
        "earning_ogn": balance/supply,
    }

def create_time_interval_report(from_block, to_block, from_block_time, to_block_time):
    decimal_context = getcontext()
    decimal_prec = decimal_context.prec
    decimal_rounding = decimal_context.rounding
    
    # to simulate uint256 in solidity when using decimals 
    decimal_context.prec = 18
    decimal_context.rounding = 'ROUND_DOWN'

    all_addresses = fetch_all_holders()

    rebase_logs = get_rebase_logs(from_block, to_block)
    analysis_list = []

    supply_data = fetch_supply_data(to_block)
    apy = get_trailing_apy(to_block)
    curve_data = get_curve_data(to_block)

    # Uncomment this to enable parallelism
    # manager = Manager()
    # analysis_list = manager.list()
    # counter = 0

    # all_chunks = chunks(all_addresses, ACCOUNT_ANALYZE_PARALLELISM)
    # for chunk in all_chunks:
    #     analyze_account_in_parallel(analysis_list, counter * ACCOUNT_ANALYZE_PARALLELISM, len(all_addresses), chunk, rebase_logs, from_block, to_block, from_block_time, to_block_time)
    #     counter += 1

    counter = 0
    for account in all_addresses:
        analyze_account(analysis_list, account, rebase_logs, from_block, to_block, from_block_time, to_block_time)
        print('Analyzing account {} of {}'.format(counter, len(all_addresses)))
        counter += 1


    accounts_analyzed = len(analysis_list)
    accounts_holding_ousd = 0
    accounts_holding_more_than_100_ousd = 0
    accounts_holding_more_than_100_ousd_after_curve_start = 0
    new_accounts = 0
    new_accounts_after_curve_start = 0
    accounts_with_non_rebase_balance_increase = 0
    accounts_with_non_rebase_balance_decrease = 0

    for analysis in analysis_list:
        accounts_holding_ousd += 1 if analysis.is_holding_ousd else 0
        accounts_holding_more_than_100_ousd += 1 if analysis.is_holding_more_than_100_ousd else 0
        accounts_holding_more_than_100_ousd_after_curve_start += 1 if analysis.new_after_curve_and_hold_more_than_100 else 0
        new_accounts += 1 if analysis.is_new_account else 0
        new_accounts_after_curve_start += 1 if analysis.is_new_after_curve_start else 0
        accounts_with_non_rebase_balance_increase += 1 if analysis.has_ousd_increased else 0
        accounts_with_non_rebase_balance_decrease += 1 if analysis.has_ousd_decreased else 0



    report = analytics_report(
        accounts_analyzed,
        accounts_holding_ousd,
        accounts_holding_more_than_100_ousd,
        accounts_holding_more_than_100_ousd_after_curve_start,
        new_accounts,
        new_accounts_after_curve_start,
        accounts_with_non_rebase_balance_increase,
        accounts_with_non_rebase_balance_decrease,
        supply_data,
        apy,
        curve_data
    )

    # set the values back again
    decimal_context.prec = decimal_prec
    decimal_context.rounding = decimal_rounding
    return report


def analyze_account_in_parallel(analysis_list, accounts_already_analyzed, total_accounts, accounts, rebase_logs, from_block, to_block, from_block_time, to_block_time):
    print("Analyzing {} accounts... progress {}/{}".format(len(accounts), accounts_already_analyzed + len(accounts), total_accounts))
    # Multiprocessing copies connection objects between processes because it forks processes
    # and therefore copies all the file descriptors of the parent process. That being said, 
    # a connection to the SQL server is just a file, you can see it in linux under /proc//fd/....
    # any open file will be shared between forked processes.
    # closing all connections just forces the processes to open new connections within the new 
    # process.
    # Not doing this causes PSQL connection errors because multiple processes are using a single connection in 
    # a non locking manner.
    db.connections.close_all()
    processes = []
    for account in accounts:
        p = Process(target=analyze_account, args=(analysis_list, account, rebase_logs, from_block, to_block, from_block_time, to_block_time, ))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

def analyze_account(analysis_list, address, rebase_logs, from_block, to_block, from_block_time, to_block_time):
    (transaction_history, previous_transfer_logs, ousd_balance, pre_curve_campaign_transfer_logs, post_curve_campaign_transfer_logs) = ensure_transaction_history(address, rebase_logs, from_block, to_block, from_block_time, to_block_time)

    is_holding_ousd = ousd_balance > 0.1
    is_holding_more_than_100_ousd = ousd_balance > 100
    is_new_account = len(previous_transfer_logs) == 0
    is_new_after_curve_start = len(pre_curve_campaign_transfer_logs) == 0
    new_after_curve_and_hold_more_than_100 = is_holding_more_than_100_ousd and is_new_after_curve_start
    non_rebase_balance_diff = 0

    for tansfer_log in filter(lambda log: isinstance(log, transfer_log), transaction_history):
        non_rebase_balance_diff += tansfer_log.amount

    analysis_list.append(
        address_analytics(is_holding_ousd, is_holding_more_than_100_ousd, is_new_account, non_rebase_balance_diff > 0, non_rebase_balance_diff < 0, is_new_after_curve_start, new_after_curve_and_hold_more_than_100)
    )

# start_time and end_time might seem redundant, but are needed so we can query the transfer logs
def ensure_analyzed_transactions(from_block, to_block, start_time, end_time, account='all'):
    tx_query = Q()
    tran_query = Q()
    if account is not 'all':
        tx_query &= Q(from_address=account) | Q(to_address=account)
        tran_query &= Q(from_address=account) | Q(to_address=account)
    # info regarding all blocks should be present
    if from_block is not None:
        tx_query &= Q(block_number__gte=from_block)
        tx_query &= Q(block_number__lt=to_block)
        tran_query &= Q(block_time__gte=start_time)
        tran_query &= Q(block_time__lt=end_time)
    
    transactions = Transaction.objects.filter(tx_query)
    transfer_transactions = map(lambda transfer: transfer.tx_hash, OusdTransfer.objects.filter(tran_query))

    analyzed_transactions = []
    analyzed_transaction_hashes = []
    
    def process_transaction(transaction):
        if transaction.tx_hash in analyzed_transaction_hashes:
            # transaction already analyzed skipping
            return

        logs = Log.objects.filter(transaction_hash=transaction.tx_hash)
        account_starting_tx = transaction.receipt_data["from"]
        contract_address = transaction.receipt_data["to"]
        internal_transactions = transaction.internal_transactions
        received_eth = len(list(filter(lambda tx: tx["to"] == account and float(tx["value"]) > 0, internal_transactions))) > 0
        sent_eth = transaction.data['value'] != '0x0'
        transfer_ousd_out = False
        transfer_ousd_in = False
        transfer_coin_out = False
        transfer_coin_in = False
        ousd_transfer_from = None
        ousd_transfer_to = None
        ousd_transfer_amount = None
        transfer_log_count = 0

        for log in logs:
            if log.topic_0 == TRANSFER:
                transfer_log_count += 1
                is_ousd_token = log.address == '0x2a8e1e676ec238d8a992307b495b45b3feaa5e86'
                from_address = "0x" + log.topic_1[-40:]
                to_address = "0x" + log.topic_2[-40:]

                if is_ousd_token: 
                    ousd_transfer_from = from_address
                    ousd_transfer_to = to_address
                    ousd_transfer_amount = int(slot(log.data, 0), 16) / E_18

                if account is not 'all':
                    if from_address == account:
                        if is_ousd_token:
                            transfer_ousd_out = True
                        else:
                            transfer_coin_out = True
                    if to_address == account:
                        if is_ousd_token:
                            transfer_ousd_in = True
                        else:
                            transfer_coin_in = True

        classification = 'unknown'
        if account is not 'all':
            swap_receive_ousd = transfer_ousd_in and (transfer_coin_out or sent_eth)
            swap_send_ousd = transfer_ousd_out and (transfer_coin_in or received_eth)

            if transfer_log_count > 0:
                if transfer_ousd_in:
                    classification = 'transfer_in'
                elif transfer_ousd_out: 
                    classification = 'transfer_out'
                else:
                    classification = 'unknown_transfer'

            if swap_receive_ousd:
                classification = 'swap_gain_ousd'
            elif swap_send_ousd:
                classification = 'swap_give_ousd'

        analyzed_transaction_hashes.append(transaction.tx_hash)
        analyzed_transactions.append(transaction_analysis(
            account_starting_tx,
            transaction.tx_hash,
            contract_address,
            internal_transactions,
            received_eth,
            sent_eth,
            transfer_ousd_out,
            transfer_ousd_in,
            transfer_coin_out,
            transfer_coin_in,
            ousd_transfer_from,
            ousd_transfer_to,
            ousd_transfer_amount,
            transfer_log_count,
            classification
        ))

    for transaction in transactions:
        process_transaction(transaction)

    for transaction in transfer_transactions:
        process_transaction(transaction)

    return analyzed_transactions

def do_transaction_analytics(from_block, to_block, start_time, end_time, account='all'):
    report = {
        'contracts_swaps': {},
        'contracts_other': {}
    }
    analyzed_transactions = ensure_analyzed_transactions(from_block, to_block, start_time, end_time, account)

    for analyzed_tx in analyzed_transactions:

        tx_hash, contract_address, received_eth, sent_eth, transfer_ousd_out, transfer_ousd_in, transfer_coin_out, transfer_coin_in, ousd_transfer_from, ousd_transfer_amount, transfer_log_count, classification = attrgetter('tx_hash', 'contract_address', 'received_eth', 'sent_eth', 'transfer_ousd_out', 'transfer_ousd_in', 'transfer_coin_out', 'transfer_coin_in', 'ousd_transfer_from', 'ousd_transfer_amount', 'transfer_log_count', 'classification')(analyzed_tx)

        if (transfer_log_count > 1 or sent_eth or received_eth) and (classification != 'swap_gain_ousd' or classification != 'swap_give_ousd'):
            print("Transaction needing further investigating hash: {}, transfer log count: {}, sent eth: {} received eth: {} coin in: {} coin out: {} ousd in: {} ousd out: {}".format(tx_hash, transfer_log_count, sent_eth, received_eth, transfer_coin_out, transfer_coin_out, transfer_ousd_in, transfer_ousd_out))    

        report_key = "contracts_swaps" if (classification == 'swap_gain_ousd' or classification == 'swap_give_ousd') else "contracts_other"
        contract_data = report[report_key][contract_address] if contract_address in report[report_key] else {
            "address": contract_address,
            "name": CONTRACT_ADDR_TO_NAME[contract_address] if contract_address in CONTRACT_ADDR_TO_NAME else "N/A",
            "total_swaps": 0,
            "total_ousd_swapped": 0,
            "total_transactions": 0
        }

        contract_data["total_transactions"] += 1
        if ousd_transfer_amount is not None:
            contract_data["total_swaps"] += 1
            contract_data["total_ousd_swapped"] += ousd_transfer_amount

        report[report_key][contract_address] = contract_data

    for report_key in ["contracts_swaps", "contracts_other"]:
        report_data = report[report_key]
        sort_key = "total_ousd_swapped" if report_key == "contracts_swaps" else "total_swaps"

        sum_total_ousd_swapped = 0
        for ousd_swapped in map(lambda report_item: report_item[1]["total_ousd_swapped"], report_data.items()):
            sum_total_ousd_swapped += ousd_swapped

        for contract_address, contract_data in report_data.items():
            contract_data["total_swapped_ousd_share"] = contract_data["total_ousd_swapped"] / sum_total_ousd_swapped if sum_total_ousd_swapped > 0 else 0

        report_data = {k: v for k, v in sorted(report_data.items(), key=lambda item: -item[1][sort_key])}
        report[report_key] = report_data

    return json.dumps(report)

def get_rebase_logs(from_block, to_block):
    # we use distinct to mitigate the problem of possibly having double logs in database
    if from_block is None and to_block is None:
        old_logs = Log.objects.filter(topic_0="0x99e56f783b536ffacf422d59183ea321dd80dcd6d23daa13023e8afea38c3df1").order_by('transaction_hash').distinct('transaction_hash')
        new_logs = Log.objects.filter(topic_0="0x41645eb819d3011b13f97696a8109d14bfcddfaca7d063ec0564d62a3e257235").order_by('transaction_hash').distinct('transaction_hash')
    else:
        old_logs = Log.objects.filter(topic_0="0x99e56f783b536ffacf422d59183ea321dd80dcd6d23daa13023e8afea38c3df1", block_number__gte=from_block, block_number__lte=to_block).order_by('transaction_hash').distinct('transaction_hash')
        new_logs = Log.objects.filter(topic_0="0x41645eb819d3011b13f97696a8109d14bfcddfaca7d063ec0564d62a3e257235", block_number__gte=from_block, block_number__lte=to_block).order_by('transaction_hash').distinct('transaction_hash')

    rebase_logs_old = list(map(lambda log: rebase_log(log.block_number, explode_log_data(log.data)[2], log.transaction_hash), old_logs))
    rebase_logs_new = list(map(lambda log: rebase_log(log.block_number, explode_log_data(log.data)[2] / 10 ** 9, log.transaction_hash), new_logs))
    rebase_logs = rebase_logs_old + rebase_logs_new

    block_numbers = list(map(lambda rebase_log: rebase_log.block_number, rebase_logs))

    blocks = list(map(lambda block: (block.block_time, block.block_number), Block.objects.filter(block_number__in=block_numbers)))
    block_lookup = dict((y, x) for x, y in blocks)

    def map_logs(log):
        log.set_block_time(block_lookup[log.block_number])
        return log

    rebase_logs = list(map(map_logs, rebase_logs))

    # rebase logs sorted by block number descending
    rebase_logs.sort(key=lambda rebase_log: -rebase_log.block_number)
    return rebase_logs


# returns a list of transfer_logs where amount is a positive number if account received OUSD
# and a negative one if OUSD was sent from the account
def get_transfer_logs(account, from_block_time, to_block_time):
    if from_block_time is None and to_block_time is None:
        transfer_logs = OusdTransfer.objects.filter((Q(from_address=account) | Q(to_address=account)))
    else:
        transfer_logs = OusdTransfer.objects.filter((Q(from_address=account) | Q(to_address=account)) & Q(block_time__gte=from_block_time) & Q(block_time__lt=to_block_time))    

    return list(map(lambda log: transfer_log(
        log.tx_hash.block_number,
        log.tx_hash,
        log.amount if log.to_address.lower() == account.lower() else -log.amount,
        log.from_address,
        log.to_address,
        log.block_time,
        log.log_index
    ), transfer_logs))

def get_history_for_address(address):
    rebase_logs = get_rebase_logs(None, None)
    hash_to_classification = dict((ana_tx.tx_hash, ana_tx.classification) for ana_tx in ensure_analyzed_transactions(None, None, None, None, address))

    (tx_history, ___, ____, _____, ______) = ensure_transaction_history(address, rebase_logs, None, None, None, None, True)

    # find last non rebase transaction, and remove later transactions
    last_non_yield_tx_idx = -1
    for i in range(len(tx_history) - 1, -1, -1):
        if not isinstance(tx_history[i], rebase_log):
            last_non_yield_tx_idx = i
            break;

    def __format_tx_history(tx_history_item):
        if isinstance(tx_history_item, rebase_log):
            return {
                'block_number': tx_history_item.block_number,
                'time': tx_history_item.block_time,
                'balance': tx_history_item.balance,
                'tx_hash': tx_history_item.tx_hash,
                'amount': tx_history_item.amount,
                'type': 'yield'
            }
        else:
            tx_hash = tx_history_item.tx_hash.tx_hash
            return {
                'block_number': tx_history_item.block_number,
                'time': tx_history_item.block_time,
                'balance': tx_history_item.balance,
                'tx_hash': tx_hash,
                'amount': tx_history_item.amount,
                'from_address': tx_history_item.from_address,
                'to_address': tx_history_item.to_address,
                'log_index' : tx_history_item.log_index,
                'type': hash_to_classification[tx_hash] if tx_hash in hash_to_classification else 'unknown_transaction_not_found'
            }

    return list(map(__format_tx_history, tx_history[:last_non_yield_tx_idx + 1 if last_non_yield_tx_idx != -1 else 0]))

# when rebase logs are available enrich transfer logs with the active credits_per_token values
def enrich_transfer_logs(logs):
    # order by ascending block number for convenience
    logs.reverse()
    logs_length = len(logs)
    current_credits_per_token = 0

    # TODO: ideally there would always be one rebase transaction before transfer once since the rebase 
    # tells us the correct value of credits_per_token at the time of the transfer transaction.
    # So when transfer is the first transaction we find the closest rebase transaction and use those
    # credits per token. Which is not correct...

    # find first credits per token
    for x in range(0, logs_length):
        log = logs[x]
        if isinstance(log, rebase_log):
            current_credits_per_token = Decimal(log.credits_per_token)
            break;

    for x in range(0, logs_length):
        log = logs[x]
        if isinstance(log, rebase_log):
            current_credits_per_token = Decimal(log.credits_per_token)
        elif isinstance(log, transfer_log):
            log.credits_per_token = current_credits_per_token
            logs[x] = log
        else:
            raise Exception('Unexpected object instance', log)

    # reverse back
    logs.reverse()
    return logs

def calculate_balance(credits, credits_per_token):
    if credits == 0 or credits_per_token == 0:
        return Decimal(0)
    return credits / credits_per_token

def ensure_ousd_balance(credit_balance, logs):
    def find_previous_rebase_log(current_index, logs):
        current_index += 1
        while(current_index < len(logs)):
            log = logs[current_index]
            if isinstance(log, rebase_log):
                return log
            current_index += 1
        return None

    for x in range(0, len(logs)):
        log = logs[x]
        if isinstance(log, rebase_log):
            log.balance = calculate_balance(credit_balance, Decimal(log.credits_per_token))
            previous_log = find_previous_rebase_log(x, logs)
            if previous_log is not None:
                prev_balance = calculate_balance(credit_balance, Decimal(previous_log.credits_per_token))
                log.amount = log.balance - prev_balance
            else:
                log.amount = 0
        elif isinstance(log, transfer_log):
            log.balance = calculate_balance(credit_balance, Decimal(log.credits_per_token))
            # multiply token balance change and credits per token at the time of the event
            credit_change = - log.amount * log.credits_per_token
            credit_balance += credit_change
        else:
            raise Exception('Unexpected object instance', log)
        logs[x] = log
    return logs

def send_report_email(summary, report, prev_report, report_type):
    report.transaction_report = json.loads(str(report.transaction_report))
    e = Email(summary, "test", render_to_string('analytics_report_email.html', {
        'type': report_type,
        'report': report,
        'change': calculate_report_change(report, prev_report),
        'stats': report_stats,
        'stat_keys': report_stats.keys(),
        'curve_stats': curve_report_stats,
        'curve_stat_keys': curve_report_stats.keys(),
    }))

    emails = settings.REPORT_RECEIVER_EMAIL_LIST.split(",")
    result = e.execute(emails)

def ensure_transaction_history(account, rebase_logs, from_block, to_block, from_block_time, to_block_time, ignore_curve_data=False):
    if rebase_logs is None:
        rebase_logs = get_rebase_logs(from_block, to_block)

    if from_block_time is None and to_block_time is None:
        transfer_logs = get_transfer_logs(account, None, None)
        previous_transfer_logs = []
    else:
        transfer_logs = get_transfer_logs(account, from_block_time, to_block_time)
        previous_transfer_logs = get_transfer_logs(account, START_OF_EVERYTHING_TIME, from_block_time)

    credit_balance, credits_per_token = creditsBalanceOf(account, to_block if to_block is not None else 'latest')

    pre_curve_campaign_transfer_logs = []
    post_curve_campaign_transfer_logs = []
    if not ignore_curve_data:
        pre_curve_campaign_transfer_logs = get_transfer_logs(account, START_OF_EVERYTHING_TIME, START_OF_CURVE_CAMPAIGN_TIME)
        post_curve_campaign_transfer_logs = get_transfer_logs(account, START_OF_CURVE_CAMPAIGN_TIME, to_block_time)

    ousd_balance = calculate_balance(credit_balance, credits_per_token)

    # filter out transactions that happened before the OUSD relaunch
    balance_logs = list(filter(lambda balance_log: balance_log.block_number > START_OF_OUSD_V2, list(transfer_logs + rebase_logs)))

    # sort transfer and rebase logs by block number descending
    balance_logs.sort(key=lambda log: -log.block_number)
    balance_logs = enrich_transfer_logs(balance_logs)
    return (ensure_ousd_balance(credit_balance, balance_logs), previous_transfer_logs, ousd_balance, pre_curve_campaign_transfer_logs, post_curve_campaign_transfer_logs)
    

