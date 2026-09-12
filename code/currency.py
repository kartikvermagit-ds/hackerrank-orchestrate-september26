"""
Deterministic Currency Conversion Layer
---------------------------------------
Performs currency conversion using ONLY fixed, dated rates from dataset/exchange_rates.csv.

Rules & Requirements:
- Home currency is taken from financial_profiles.csv.
- Matches rates according to challenge specification:
  - Exact match on settlement_date (or event_date if settlement_date is blank).
  - Direct conversion direction (from_currency -> to_currency).
  - Inverse rate derivation (1.0 / rate) when reverse direction is needed.
  - Cross-rate routing via intermediate USD or EUR for indirect pairs.
  - Closest available date matching when an exact calendar date is between monthly rate points.
- Zero live banking, market data, or external API calls.
- Preserves full 64-bit floating point precision.
- 100% deterministic.
"""

from typing import Dict, Tuple, List, Optional
import pandas as pd
import numpy as np

class CurrencyConverter:
    """Deterministic currency conversion engine backed solely by fixed exchange_rates.csv."""

    SUPPORTED_CURRENCIES = {'INR', 'ZAR', 'IDR', 'USD', 'EUR'}

    def __init__(self, exchange_rates_df: pd.DataFrame):
        # Direct rates map: (rate_date, from_currency, to_currency) -> rate
        self.direct_rates: Dict[Tuple[str, str, str], float] = {}
        # Inverted rates map: (rate_date, from_currency, to_currency) -> 1.0 / rate
        self.inverse_rates: Dict[Tuple[str, str, str], float] = {}
        # Available dates per pair: (from_currency, to_currency) -> sorted list of date strings
        self.pair_dates: Dict[Tuple[str, str], List[str]] = {}

        for _, row in exchange_rates_df.iterrows():
            d = str(row['rate_date']).strip()
            # Standardize date to YYYY-MM-DD
            dt_str = pd.to_datetime(d).strftime('%Y-%m-%d')
            f = str(row['from_currency']).strip().upper()
            t = str(row['to_currency']).strip().upper()
            r = float(row['rate'])

            self.direct_rates[(dt_str, f, t)] = r
            self.pair_dates.setdefault((f, t), []).append(dt_str)

            if r > 0:
                inv_r = 1.0 / r
                self.inverse_rates[(dt_str, t, f)] = inv_r
                self.pair_dates.setdefault((t, f), []).append(dt_str)

        # Sort date lists
        for pair in self.pair_dates:
            self.pair_dates[pair] = sorted(list(set(self.pair_dates[pair])))

    def _get_closest_date(self, target_date: str, available_dates: List[str]) -> str:
        """Find the closest calendar date among available rate dates."""
        target_dt = pd.to_datetime(target_date)
        return min(available_dates, key=lambda d: abs((pd.to_datetime(d) - target_dt).days))

    def get_rate(self, from_curr: str, to_curr: str, rate_date: str) -> float:
        """
        Get exchange rate for currency pair on rate_date.
        Deterministic fallback hierarchy:
        1. Exact direct match (rate_date, from_curr, to_curr)
        2. Exact inverse match (rate_date, to_curr, from_curr)
        3. Closest date direct match
        4. Closest date inverse match
        5. Cross-rate via USD or EUR
        """
        f = from_curr.strip().upper()
        t = to_curr.strip().upper()

        if f == t:
            return 1.0

        d_str = pd.to_datetime(rate_date).strftime('%Y-%m-%d')

        # 1. Exact direct rate
        if (d_str, f, t) in self.direct_rates:
            return self.direct_rates[(d_str, f, t)]

        # 2. Exact inverse rate
        if (d_str, f, t) in self.inverse_rates:
            return self.inverse_rates[(d_str, f, t)]

        # 3 & 4. Closest available date for the direct or inverse pair
        if (f, t) in self.pair_dates and self.pair_dates[(f, t)]:
            closest_d = self._get_closest_date(d_str, self.pair_dates[(f, t)])
            if (closest_d, f, t) in self.direct_rates:
                return self.direct_rates[(closest_d, f, t)]
            if (closest_d, f, t) in self.inverse_rates:
                return self.inverse_rates[(closest_d, f, t)]

        # 5. Cross-rate via USD or EUR
        for intermediate in ['USD', 'EUR']:
            if intermediate not in (f, t):
                try:
                    r1 = self.get_rate(f, intermediate, d_str)
                    r2 = self.get_rate(intermediate, t, d_str)
                    return r1 * r2
                except ValueError:
                    continue

        raise ValueError(f"No exchange rate path available from '{from_curr}' to '{to_curr}' for date '{rate_date}'")

    def convert(self, amount: Optional[float], from_curr: str, to_curr: str, rate_date: str) -> float:
        """
        Convert monetary amount from from_curr to to_curr using rate on rate_date.
        Preserves full float precision.
        """
        if amount is None or amount == 0.0:
            return 0.0

        f = from_curr.strip().upper()
        t = to_curr.strip().upper()

        if f == t:
            return float(amount)

        rate = self.get_rate(f, t, rate_date)
        return float(amount) * rate
