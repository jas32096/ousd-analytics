from decimal import Decimal
from enum import Enum
from statistics import mean
from core.blockchain.addresses import CONTRACT_ADDR_TO_NAME
from core.blockchain.const import (
    CTOKEN_DECIMALS,
    DECIMALS_FOR_SYMBOL,
    SYMBOL_FOR_COMPOUND,
)
from core.blockchain.conversion import ctoken_to_underlying
from core.common import Direction, dict_append, format_decimal
from notify.events import event_critical, event_high, event_normal

PERCENT_DIFF_THRESHOLD_NOTICE = {
    'default': Decimal(0.05),
    'usdt': Decimal(0.1),
}
PERCENT_DIFF_THRESHOLD_WARNING = {
    'default': Decimal(0.10),
    'usdt': Decimal(0.2),
}
PERCENT_DIFF_THRESHOLD_CRITICAL = {
    'default': Decimal(0.15),
    'usdt': Decimal(0.3),
}


def get_past_comparison(ctoken_snaps):
    """ Get the historical comparison value.  It will either be an average of
    past values, last value, or 0, depending on what is available. """

    count = len(ctoken_snaps)

    if count < 2:
        return 0

    elif count > 2:
        return mean([x.total_supply for x in ctoken_snaps[1:]])

    return ctoken_snaps[1].total_supply


def create_message(action, ctoken_name, diff, diff_underlying, symbol,
                   pct_threshold, emoji):
    dir_symbol = "+" if action == Direction.GAIN else "-"
    dir_desc = "gained" if action == Direction.GAIN else "lost"
    title = "Compound cToken Total Supply Fluctuation   {}".format(emoji)
    msg = (
        "The cToken {} has {} more than ({}%) between "
        "snapshots.\n\n"
        "c{}: {}{}\n"
        "{} (approx): {}{}".format(
            ctoken_name,
            dir_desc,
            round(pct_threshold * Decimal(100)),
            symbol,
            dir_symbol,
            format_decimal(diff, max_decimals=CTOKEN_DECIMALS),
            symbol,
            dir_symbol,
            format_decimal(
                diff_underlying,
                max_decimals=DECIMALS_FOR_SYMBOL.get(symbol, 4)
            ),
        )
    )

    return title, msg


def run_trigger(recent_ctoken_snapshots):
    """ Trigger on extreme supply changes in cTokens """
    events = []
    snaps = {}

    for snap in recent_ctoken_snapshots:
        dict_append(snaps, snap.address, snap)

    for ctoken_address in snaps:
        title = ""
        msg = ""
        ev_func = event_normal
        emoji = "🚨"
        threshold = None
        underlying_symbol = SYMBOL_FOR_COMPOUND.get(ctoken_address, '')

        threshold_notice = PERCENT_DIFF_THRESHOLD_NOTICE.get(
            underlying_symbol,
            PERCENT_DIFF_THRESHOLD_NOTICE['default']
        )
        threshold_warning = PERCENT_DIFF_THRESHOLD_WARNING.get(
            underlying_symbol,
            PERCENT_DIFF_THRESHOLD_WARNING['default']
        )
        threshold_critical = PERCENT_DIFF_THRESHOLD_CRITICAL.get(
            underlying_symbol,
            PERCENT_DIFF_THRESHOLD_CRITICAL['default']
        )

        total_supply_comp = get_past_comparison(snaps[ctoken_address])
        total_supply_current = snaps[ctoken_address][0].total_supply
        notice_diff_threshold = total_supply_comp * threshold_notice
        warning_diff_threshold = total_supply_comp * threshold_warning
        critical_diff_threshold = total_supply_comp * threshold_critical

        if total_supply_current < total_supply_comp:
            diff = total_supply_comp - total_supply_current
            direction = Direction.LOSS

            if diff > critical_diff_threshold:
                ev_func = event_critical
                threshold = threshold_critical
            elif diff > warning_diff_threshold:
                ev_func = event_high
                threshold = threshold_warning
            elif diff > notice_diff_threshold:
                ev_func = event_normal
                threshold = threshold_notice
                emoji = "📉"

            underlying_diff = ctoken_to_underlying(
                underlying_symbol,
                diff,
                snap.block_number
            )

            if threshold:
                title, msg = create_message(
                    direction,
                    CONTRACT_ADDR_TO_NAME.get(
                        ctoken_address,
                        ctoken_address
                    ),
                    diff,
                    underlying_diff,
                    underlying_symbol,
                    threshold,
                    emoji=emoji
                )

        else:
            diff = total_supply_current - total_supply_comp
            direction = Direction.GAIN

            if diff > critical_diff_threshold:
                ev_func = event_critical
                threshold = threshold_critical
            elif diff > warning_diff_threshold:
                ev_func = event_high
                threshold = threshold_warning
            elif diff > notice_diff_threshold:
                ev_func = event_normal
                threshold = threshold_notice
                emoji = "📈"

            underlying_diff = ctoken_to_underlying(
                underlying_symbol,
                diff,
                snap.block_number
            )

            if threshold:
                title, msg = create_message(
                    direction,
                    CONTRACT_ADDR_TO_NAME.get(
                        ctoken_address,
                        ctoken_address
                    ),
                    diff,
                    underlying_diff,
                    underlying_symbol,
                    threshold,
                    emoji=emoji
                )

        if title:
            events.append(ev_func(
                title,
                msg,
                block_number=snaps[ctoken_address][0].block_number
            ))

    return events
