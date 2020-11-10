from decimal import Decimal
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from core.blockchain import (
    build_asset_block,
    build_debug_tx,
    ensure_supply_snapshot,
    ensure_asset,
    lastest_block,
    ensure_latest_logs,
    download_logs_from_contract,
    totalSupply,
    balanceOf,
)
from core.models import AssetBlock, DebugTx, LogPointer, Log, SupplySnapshot

import core.blockchain as blockchain
import datetime

BLOCKS_PER_DAY = 6500


def dashboard(request):
    block_number = _latest_snapshot_block_number()

    dai = ensure_asset("DAI", block_number)
    usdt = ensure_asset("USDT", block_number)
    usdc = ensure_asset("USDC", block_number)

    apy = _get_trailing_apy()

    assets = [dai, usdt, usdc]
    total_vault = sum(x.vault_holding for x in assets)
    total_aave = sum(x.aavestrat_holding for x in assets)
    total_compstrat = sum(x.compstrat_holding for x in assets)
    total_threepool = sum(x.threepoolstrat_holding for x in assets)
    total_assets = sum(x.total() for x in assets)
    total_supply = totalSupply(blockchain.OUSD, 18, block_number)
    total_value = sum(x.redeem_value() for x in assets)
    extra_assets = total_assets - total_supply
    extra_value = total_value - total_supply

    ensure_latest_logs(block_number)

    logs_q = Log.objects.all()
    topic = request.GET.get("topic_0")
    if topic:
        logs_q = logs_q.filter(topic_0=topic)
    latest_logs = logs_q[:100]

    filters = [
        {
            "topic": "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            "label": "transfers",
        },
        {
            "topic": "0x0f6798a560793a54c3bcfe86a93cde1e73087d944c0ea20544137d4121396885",
            "label": "mints",
        },
        {
            "topic": "0x222838db2794d11532d940e8dec38ae307ed0b63cd97c233322e221f998767a6",
            "label": "redeems",
        },
        {
            "topic": "0xa560e3198060a2f10670c1ec5b403077ea6ae93ca8de1c32b451dc1a943cd6e7",
            "label": "governance",
        },
        {
            "topic": "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822",
            "label": "swaps",
        },
    ]

    return _cache(20, render(request, "dashboard.html", locals()))


def reload(request):
    latest = lastest_block()
    _reload(latest - 2)
    _reload(latest - 2 - BLOCKS_PER_DAY * 7)  # Week ago, for APR
    return HttpResponse("ok")


def apr_index(request):
    STEP = BLOCKS_PER_DAY
    NUM_STEPS = 15
    latest_block_number = _latest_snapshot_block_number()
    end_block_number = latest_block_number - latest_block_number % STEP
    rows = []
    last_snapshot = None
    block_numbers = list(
        range(end_block_number - (NUM_STEPS - 1) * STEP, end_block_number + 1, STEP)
    ) + [latest_block_number]
    for block_number in block_numbers:
        s = ensure_supply_snapshot(block_number)
        if last_snapshot:
            blocks = s.block_number - last_snapshot.block_number
            change = (
                s.rebasing_credits_ratio / last_snapshot.rebasing_credits_ratio
            ) - Decimal(1)
            s.apr = Decimal(100) * change / blocks * Decimal(365) * BLOCKS_PER_DAY
            s.gain = change * s.computed_supply
        rows.append(s)
        last_snapshot = s
    rows.reverse()
    seven_day_apy = _get_trailing_apy()

    # Running for today
    today_adjust = Decimal(
        (latest_block_number - end_block_number) / float(BLOCKS_PER_DAY)
    )
    rows[0].apr = rows[0].apr / today_adjust

    # drop last row with incomplete information
    rows = rows[:-1]
    return _cache(5 * 60, render(request, "apr_index.html", locals()))


def api_apr_trailing(request):
    apr = _get_trailing_apr()
    if apr < 0:
        apr = "0"
    apy = _get_trailing_apy()
    if apy < 0:
        apy = 0
    response = JsonResponse({"apr": apr, "apy": apy})
    response.setdefault("Access-Control-Allow-Origin", "*")
    return _cache(120, response)


def api_speed_test(request):
    return _cache(120, JsonResponse({"test": "test"}))


def address(request, address):
    if address != address.lower():
        return redirect("address", address=address.lower())
    long_address = address.replace("0x", "0x000000000000000000000000")
    latest_block_number = _latest_snapshot_block_number()
    transfers = Log.objects.filter(
        address=blockchain.OUSD, topic_0=blockchain.TRANSFER
    ).filter(Q(topic_1=long_address) | Q(topic_2=long_address))
    transfers_in = sum([x.ousd_value() for x in transfers if x.topic_2 == long_address])
    transfers_out = sum(
        [x.ousd_value() for x in transfers if x.topic_1 == long_address]
    )
    current_balance = balanceOf(blockchain.OUSD, address, 18)
    non_yield_balance = transfers_in - transfers_out
    yield_balance = current_balance - non_yield_balance
    return render(request, "address.html", locals())


def _my_assets(address, block_number):
    dai = ensure_asset("DAI", block_number)
    usdt = ensure_asset("USDT", block_number)
    usdc = ensure_asset("USDC", block_number)
    total_supply = totalSupply(blockchain.OUSD, 18, block_number)

    current_balance = blockchain.balanceOf(blockchain.OUSD, address, 18, block_number)
    total_supply = totalSupply(blockchain.OUSD, 18, block_number)

    return {
        "my": {
            "DAI": (dai.vault_holding + dai.compstrat_holding)
            * current_balance
            / total_supply,
            "USDC": (usdc.vault_holding + usdc.compstrat_holding)
            * current_balance
            / total_supply,
            "USDT": (usdt.vault_holding + usdt.compstrat_holding)
            * current_balance
            / total_supply,
        },
        "current_balance": current_balance,
        "total_supply": total_supply,
    }


def tx_debug(request, tx_hash):
    debug_tx = ensure_debug_tx(tx_hash)
    return _cache(1200, render(request, "debug_tx.html", locals()))


def ensure_debug_tx(tx_hash):
    if DebugTx.objects.filter(tx_hash=tx_hash).count() == 0:
        ab = build_debug_tx(tx_hash)
        ab.save()
    else:
        ab = DebugTx.objects.filter(tx_hash=tx_hash).first()
    return ab


def _cache(seconds, response):
    response.setdefault("Cache-Control", "public, max-age=%d" % seconds)
    response.setdefault("Vary", "Accept-Encoding")
    return response


def _reload(block_number):
    dai = ensure_asset("DAI", block_number)
    usdt = ensure_asset("USDT", block_number)
    usdc = ensure_asset("USDC", block_number)
    ensure_latest_logs(block_number)
    ensure_supply_snapshot(block_number)


def _latest_snapshot_block_number():
    latest = SupplySnapshot.objects.order_by("-block_number")[0]
    return latest.block_number


PREV_APR = None


def _get_trailing_apr():
    days = 7
    # Check cache first
    global PREV_APR
    if PREV_APR:
        good_to, apr = PREV_APR
        if good_to > datetime.datetime.today():
            return apr
    # Calculate
    end_block_number = _latest_snapshot_block_number()
    # Comment this out for live trailing
    # end_block_number = end_block_number - end_block_number % BLOCKS_PER_DAY
    week_block_number = end_block_number - BLOCKS_PER_DAY * days
    today = ensure_supply_snapshot(end_block_number)
    weekago = ensure_supply_snapshot(week_block_number)

    seven_day_apr = (
        ((today.rebasing_credits_ratio / weekago.rebasing_credits_ratio) - Decimal(1))
        * Decimal(100)
        * Decimal(365.25)
        / Decimal(days)
    )
    seven_day_apr = round(seven_day_apr, 2)
    good_to = datetime.datetime.today() + datetime.timedelta(minutes=5)
    PREV_APR = [good_to, seven_day_apr]
    return seven_day_apr


def _get_trailing_apy():
    apr = Decimal(_get_trailing_apr())
    periods_per_year = Decimal(365.25 / 7.0)
    apy = ((1 + apr / periods_per_year / 100) ** periods_per_year - 1) * 100
    return round(apy, 2)
