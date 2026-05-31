"""
Thin shim. The real engine moved to valuation.py (multi-factor: ratings + comps + DCF).
This file exists only so scoring.py's existing import keeps working.

To get the FULL valuation dict (intrinsic, peer percentiles, etc.), call
valuation.valuation_for_ticker(ticker) directly instead.
"""
import valuation


def cheapness_0_1(ticker):
    """0..1 cheapness (1=cheap), or None when FMP key unset / lookup fails."""
    return valuation.cheapness_0_1(ticker)
