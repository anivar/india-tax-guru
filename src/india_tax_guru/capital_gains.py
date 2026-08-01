"""Capital gains: bucketing, inter-head set-off, and tax at special rates.

Edge cases handled:
- s.50AA: specified mutual funds (debt-oriented funds acquired on or after 1 April 2023,
  and market-linked debentures) are deemed SHORT-TERM regardless of holding period and
  taxed at slab rates. Enforced in `CapitalGainLot.__post_init__`, so a caller cannot
  smuggle one through as long-term and get 12.5%.
- Set-off ordering (s.70/74): a SHORT-term capital loss may be set off against both
  short- and long-term gains; a LONG-term capital loss may be set off ONLY against
  long-term gains. Capital losses may never be set off against other heads. Short-term
  losses are therefore consumed against short-term gains first (preserving the more
  flexible relief for later), and long-term losses only against long-term gains.
- Non-equity SHORT-term gains are taxed at slab rates, not a special rate, so they are
  returned as an amount to fold into normal income rather than taxed here.
- The s.112A annual exemption applies to equity long-term gains only, and is applied
  before any basic-exemption set-off.
- A RESIDENT individual whose other income falls short of the basic exemption limit may
  set the shortfall off against capital gains (proviso to s.111A/112A). Applied against
  the highest-taxed gains first, which is the taxpayer-favourable ordering. Not
  available to non-residents — hence `TaxpayerProfile.is_resident`.
- Unabsorbed capital losses are REPORTED, not silently zeroed. Carry-forward across
  assessment years (s.74) is out of scope for a single-year calculator.
"""

from dataclasses import dataclass, field

from .models import CapitalGainLot
from .rules.base import AssessmentYearRules


@dataclass(frozen=True)
class CapitalGainBuckets:
    equity_stcg: int  # s.111A, flat rate
    equity_ltcg: int  # s.112A, flat rate after the annual exemption
    other_stcg: int  # slab rate — folded into normal income by the caller
    other_ltcg: int  # s.112, flat rate
    unabsorbed_short_term_loss: int
    unabsorbed_long_term_loss: int
    notes: list[str] = field(default_factory=list)


def bucket_capital_gains(lots: list[CapitalGainLot]) -> CapitalGainBuckets:
    equity_st = sum(lot.gain for lot in lots if lot.is_equity and not lot.is_long_term)
    equity_lt = sum(lot.gain for lot in lots if lot.is_equity and lot.is_long_term)
    other_st = sum(lot.gain for lot in lots if not lot.is_equity and not lot.is_long_term)
    other_lt = sum(lot.gain for lot in lots if not lot.is_equity and lot.is_long_term)

    st_gains = {"equity": max(0, equity_st), "other": max(0, other_st)}
    lt_gains = {"equity": max(0, equity_lt), "other": max(0, other_lt)}
    st_loss = -min(0, equity_st) - min(0, other_st)
    lt_loss = -min(0, equity_lt) - min(0, other_lt)

    notes: list[str] = []

    def _consume(loss: int, pools: dict[str, int], order: list[str]) -> int:
        for key in order:
            if loss <= 0:
                break
            absorbed = min(loss, pools[key])
            pools[key] -= absorbed
            loss -= absorbed
        return loss

    # Long-term losses: long-term gains only.
    lt_loss = _consume(lt_loss, lt_gains, ["equity", "other"])

    # Short-term losses: short-term gains first, then long-term gains.
    st_loss = _consume(st_loss, st_gains, ["equity", "other"])
    st_loss = _consume(st_loss, lt_gains, ["equity", "other"])

    if st_loss > 0 or lt_loss > 0:
        notes.append(
            f"Unabsorbed capital loss this year: short-term {st_loss:,}, long-term {lt_loss:,}. "
            "Carry-forward to future years (s.74) is not modelled by this tool."
        )

    return CapitalGainBuckets(
        equity_stcg=st_gains["equity"],
        equity_ltcg=lt_gains["equity"],
        other_stcg=st_gains["other"],
        other_ltcg=lt_gains["other"],
        unabsorbed_short_term_loss=st_loss,
        unabsorbed_long_term_loss=lt_loss,
        notes=notes,
    )


@dataclass(frozen=True)
class CapitalGainsTax:
    taxable_equity_stcg: int
    taxable_equity_ltcg: int  # after the s.112A annual exemption
    taxable_other_ltcg: int
    basic_exemption_used: int
    tax: int
    notes: list[str] = field(default_factory=list)


def tax_on_special_rate_gains(
    buckets: CapitalGainBuckets,
    rules: AssessmentYearRules,
    basic_exemption_headroom: int = 0,
) -> CapitalGainsTax:
    """Tax on gains charged at special rates (everything except slab-rate short-term).

    `basic_exemption_headroom` is the unused portion of the taxpayer's basic exemption
    limit after normal income — pass 0 for a non-resident, who cannot claim it.
    """
    notes: list[str] = []

    equity_stcg = buckets.equity_stcg
    equity_ltcg = max(0, buckets.equity_ltcg - rules.ltcg_112a_exemption)
    other_ltcg = buckets.other_ltcg

    # Apply basic-exemption headroom to the highest-taxed gains first.
    headroom = max(0, basic_exemption_headroom)
    used = 0
    by_rate = [
        ("equity_stcg", rules.stcg_111a_rate),
        ("equity_ltcg", rules.ltcg_112a_rate),
        ("other_ltcg", rules.ltcg_other_rate),
    ]
    amounts = {"equity_stcg": equity_stcg, "equity_ltcg": equity_ltcg, "other_ltcg": other_ltcg}
    for key, _rate in sorted(by_rate, key=lambda kr: -kr[1]):
        if headroom <= 0:
            break
        absorbed = min(headroom, amounts[key])
        amounts[key] -= absorbed
        headroom -= absorbed
        used += absorbed

    if used > 0:
        notes.append(
            f"Unused basic exemption of {used:,} set off against capital gains "
            "(proviso to s.111A/112A, residents only)."
        )

    tax = (
        round(amounts["equity_stcg"] * rules.stcg_111a_rate)
        + round(amounts["equity_ltcg"] * rules.ltcg_112a_rate)
        + round(amounts["other_ltcg"] * rules.ltcg_other_rate)
    )

    return CapitalGainsTax(
        taxable_equity_stcg=amounts["equity_stcg"],
        taxable_equity_ltcg=amounts["equity_ltcg"],
        taxable_other_ltcg=amounts["other_ltcg"],
        basic_exemption_used=used,
        tax=tax,
        notes=notes,
    )
