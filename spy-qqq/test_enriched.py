import unittest
import pandas as pd
from enriched_features import enrich
from jev_market_test import paper_decision, leveraged_choice


def candles(n=250):
    dates = pd.bdate_range('2025-01-01', periods=n)
    v = [100 + i * 0.2 for i in range(n)]
    return pd.DataFrame({'Open':[x-0.1 for x in v], 'High':[x+0.5 for x in v],
                         'Low':[x-0.6 for x in v], 'Close':v, 'Volume':[10000]*n},
                        index=[d.date().isoformat() for d in dates])

class EnrichedTest(unittest.TestCase):
    def test_directions(self):
        self.assertEqual(leveraged_choice('QQQ', .49), 'SQQQ')
        self.assertEqual(leveraged_choice('QQQ', .50), 'TQQQ')
        self.assertEqual(paper_decision(.49), 'PAPER_BEAR_3X')

    def test_data_cutoff_no_lookahead(self):
        df = candles()
        cutoff = df.index[230]
        def loader(_):
            return df.copy()
        one = enrich(df, cutoff, 'SPY', loader=loader)
        edited = df.copy()
        edited.loc[edited.index > cutoff, 'Close'] = 99999
        two = enrich(edited, cutoff, 'SPY', loader=lambda _: edited)
        self.assertEqual(one, two)
        self.assertEqual(one['data_cutoff_session'], cutoff)

    def test_missing_cross_assets(self):
        df = candles()
        data = enrich(df, df.index[-1], 'SPY', loader=lambda _: (_ for _ in ()).throw(ValueError('offline')))
        self.assertEqual(len(data['cross_assets']), 0)
        self.assertGreater(len(data['unavailable_cross_assets']), 0)

    def test_old_csv_schema_migrates(self):
        # Rows written by the earlier multi-backend harness carry a "backend"
        # column this version dropped. Reading + rewriting them must not crash
        # (the baseline cohort reuses predictions.csv).
        import csv as csvmod
        import tempfile
        from pathlib import Path
        import jev_market_test as m
        old_fields = ["predicted_at_utc", "symbol", "backend", "as_of_date", "model",
                      "p_up", "direction", "decision", "features_json", "target_date",
                      "next_open", "next_close", "was_up", "intraday_return",
                      "long_trade_net", "benchmark_always_long_net"]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "predictions.csv"
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csvmod.DictWriter(f, fieldnames=old_fields)
                w.writeheader()
                w.writerow({k: ("minicpm" if k == "backend" else "x") for k in old_fields})
            old_data_file = m.DATA_FILE
            m.DATA_FILE = p
            try:
                rows = m.read_rows()
                m.write_rows(rows)  # must not raise ValueError
                rows2 = m.read_rows()
            finally:
                m.DATA_FILE = old_data_file
        self.assertEqual(len(rows2), 1)
        self.assertNotIn("backend", rows2[0])
        self.assertEqual(rows2[0]["leveraged_symbol"], "")

if __name__ == '__main__': unittest.main()
