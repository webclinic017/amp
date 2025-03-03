"""
Import as:

import dataflow.model.forecast_evaluator_from_prices as dtfmfefrpr
"""

import logging
import os
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd

import core.finance as cofinanc
import core.signal_processing as sigproc
import helpers.hdbg as hdbg
import helpers.hio as hio
import helpers.hpandas as hpandas

_LOG = logging.getLogger(__name__)


class ForecastEvaluatorFromPrices:
    """
    Evaluate returns/volatility forecasts.
    """

    def __init__(
        self,
        price_col: str,
        volatility_col: str,
        prediction_col: str,
    ) -> None:
        """
        Initialize column names.

        Note:
        - the `price_col` is unadjusted price (no adjustment for splits,
          dividends, or volatility)
        - the `volatility_col` is used for position sizing
        - the `prediction_col` is a prediction of vol-adjusted returns
          (presumably with volatility given by `volatility_col`)

        :param price_col: price per share
        :param volatility_col: volatility used for adjustment of forward returns
        :param prediction_col: prediction of volatility-adjusted returns, two
            steps ahead
        """
        # Initialize dataframe columns.
        hdbg.dassert_isinstance(price_col, str)
        self._price_col = price_col
        hdbg.dassert_isinstance(volatility_col, str)
        self._volatility_col = volatility_col
        hdbg.dassert_isinstance(prediction_col, str)
        self._prediction_col = prediction_col

    @staticmethod
    def read_portfolio(
        log_dir: str,
        *,
        file_name: Optional[str] = None,
        tz: str = "America/New_York",
        cast_asset_ids_to_int: bool = True,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Read and process logged portfolio.

        :param file_name: if `None`, find and use the latest
        """
        if file_name is None:
            dir_name = os.path.join(log_dir, "price")
            pattern = "*"
            only_files = True
            use_relative_paths = True
            files = hio.listdir(dir_name, pattern, only_files, use_relative_paths)
            files.sort()
            file_name = files[-1]
            _LOG.info("`file_name`=%s", file_name)
        price = ForecastEvaluatorFromPrices._read_df(
            log_dir, "price", file_name, tz
        )
        volatility = ForecastEvaluatorFromPrices._read_df(
            log_dir, "volatility", file_name, tz
        )
        predictions = ForecastEvaluatorFromPrices._read_df(
            log_dir, "prediction", file_name, tz
        )
        holdings = ForecastEvaluatorFromPrices._read_df(
            log_dir, "holdings", file_name, tz
        )
        positions = ForecastEvaluatorFromPrices._read_df(
            log_dir, "position", file_name, tz
        )
        flows = ForecastEvaluatorFromPrices._read_df(
            log_dir, "flow", file_name, tz
        )
        pnl = ForecastEvaluatorFromPrices._read_df(log_dir, "pnl", file_name, tz)
        if cast_asset_ids_to_int:
            for df in [
                price,
                volatility,
                predictions,
                holdings,
                positions,
                flows,
                pnl,
            ]:
                ForecastEvaluatorFromPrices._cast_cols_to_int(df)
        portfolio_df = ForecastEvaluatorFromPrices._build_multiindex_df(
            price,
            volatility,
            predictions,
            holdings,
            positions,
            flows,
            pnl,
        )
        statistics_df = ForecastEvaluatorFromPrices._read_df(
            log_dir, "statistics", file_name, tz
        )
        return portfolio_df, statistics_df

    def to_str(
        self,
        df: pd.DataFrame,
        **kwargs,
    ) -> str:
        """
        Return the state of the Portfolio as a string.

        :param df: as in `compute_portfolio`
        :param target_gmv: as in `compute_portfolio`
        :param dollar_neutrality: as in `compute_portfolio`
        """
        holdings, positions, flows, pnl, stats = self.compute_portfolio(
            df,
            **kwargs,
        )
        act = []
        round_precision = 6
        precision = 2
        act.append(
            "# holdings=\n%s"
            % hpandas.df_to_str(
                holdings.round(round_precision),
                num_rows=None,
                precision=precision,
            )
        )
        act.append(
            "# holdings marked to market=\n%s"
            % hpandas.df_to_str(
                positions.round(round_precision),
                num_rows=None,
                precision=precision,
            )
        )
        act.append(
            "# flows=\n%s"
            % hpandas.df_to_str(
                flows.round(round_precision),
                num_rows=None,
                precision=precision,
            )
        )
        act.append(
            "# pnl=\n%s"
            % hpandas.df_to_str(
                pnl.round(round_precision),
                num_rows=None,
                precision=precision,
            )
        )
        act.append(
            "# statistics=\n%s"
            % hpandas.df_to_str(
                stats.round(round_precision), num_rows=None, precision=precision
            )
        )
        act = "\n".join(act)
        return act

    def log_portfolio(
        self,
        df: pd.DataFrame,
        log_dir: str,
        **kwargs,
    ) -> str:
        hdbg.dassert(log_dir, "Must specify `log_dir` to log portfolio.")
        holdings, position, flow, pnl, statistics = self.compute_portfolio(
            df,
            **kwargs,
        )
        last_timestamp = df.index[-1]
        hdbg.dassert_isinstance(last_timestamp, pd.Timestamp)
        last_timestamp_str = last_timestamp.strftime("%Y%m%d_%H%M%S")
        file_name = f"{last_timestamp_str}.csv"
        #
        ForecastEvaluatorFromPrices._write_df(
            df[self._price_col], log_dir, "price", file_name
        )
        ForecastEvaluatorFromPrices._write_df(
            df[self._volatility_col], log_dir, "volatility", file_name
        )
        ForecastEvaluatorFromPrices._write_df(
            df[self._prediction_col], log_dir, "prediction", file_name
        )
        ForecastEvaluatorFromPrices._write_df(
            holdings, log_dir, "holdings", file_name
        )
        ForecastEvaluatorFromPrices._write_df(
            position, log_dir, "position", file_name
        )
        ForecastEvaluatorFromPrices._write_df(flow, log_dir, "flow", file_name)
        ForecastEvaluatorFromPrices._write_df(pnl, log_dir, "pnl", file_name)
        ForecastEvaluatorFromPrices._write_df(
            statistics, log_dir, "statistics", file_name
        )
        return file_name

    def compute_portfolio(
        self,
        df: pd.DataFrame,
        *,
        bulk_frac_to_remove: float = 0.0,
        bulk_fill_method: str = "zero",
        target_gmv: Union[float, pd.Series] = 1e6,
        quantization: str = "no_quantization",
        reindex_like_input: bool = False,
        burn_in_bars: int = 3,
    ) -> Tuple[
        pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
    ]:
        """
        Compute target positions, PnL, and portfolio stats.

        :param df: multiindexed dataframe with predictions, returns, volatility
        :param bulk_frac_to_remove: applied to predictions; as in
            `csigproc.gaussian_rank()`
        :param bulk_fill_method: applied to predictions; as in
            `csigproc.gaussian_rank()`
        :param target_gmv: a float (constant target GMV) or else a
            `datetime.time` indexed `pd.Series` of GMVs (e.g., to simulate
            intraday ramp-up/ramp-down)
        :param reindex_like_input: output dataframes to have the same input as
            `df` (e.g., including any weekends or values outside of the
            `start_time`-`end_time` range)
        :param quantization: indicate whether to round to nearest share, lot
        :param reindex_like_input: if `False`, only return dataframes indexed
            by the inferred "active index" of datetimes
        :param burn_in_bars: number of leading bars to trim (to remove warm-up
            artifacts)
        :return: (holdings, position, flow, pnl, stats)
        """
        self._validate_df(df)
        # Record index in case we reindex the results.
        if reindex_like_input:
            idx = df.index
        df = self._apply_trimming(df)
        # Extract prediction and volatility dataframes.
        prediction_df = ForecastEvaluatorFromPrices._get_df(
            df, self._prediction_col
        )
        volatility_df = ForecastEvaluatorFromPrices._get_df(
            df, self._volatility_col
        )
        # The values of`target_positions` represent cash values.
        target_positions = (
            ForecastEvaluatorFromPrices._compute_target_positions_from_forecasts(
                volatility_df,
                prediction_df,
                bulk_frac_to_remove,
                bulk_fill_method,
                target_gmv,
            )
        )
        # Compute target holdings.
        price_df = ForecastEvaluatorFromPrices._get_df(df, self._price_col)
        holdings, flows = self._compute_holdings_and_flows(
            price_df, target_positions, quantization=quantization
        )
        # Current positions in dollars.
        positions = holdings.multiply(price_df)
        pnl = positions.diff().add(flows, fill_value=0)
        # Compute statistics.
        stats = self._compute_statistics(positions, flows, pnl)
        # Remove initial bars.
        if burn_in_bars > 0:
            holdings = holdings.iloc[burn_in_bars:]
            positions = positions.iloc[burn_in_bars:]
            flows = flows.iloc[burn_in_bars:]
            pnl = pnl.iloc[burn_in_bars:]
            stats = stats.iloc[burn_in_bars:]
        # Convert one-step-ahead target positions to "point-in-time"
        # (hypothetically) realized positions.
        # Possibly reindex dataframes.
        if reindex_like_input:
            holdings = holdings.reindex(idx)
            positions = positions.reindex(idx)
            flows = flows.reindex(idx)
            pnl = pnl.reindex(idx)
            stats = stats.reindex(idx)
        return holdings, positions, flows, pnl, stats

    def annotate_forecasts(
        self,
        df: pd.DataFrame,
        **kwargs,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Wraps `compute_portfolio()`, returns a single multiindexed dataframe.

        :param df: as in `compute_portfolio()`
        :param target_gmv: as in `compute_portfolio()`
        :param dollar_neutrality: as in `compute_portfolio()`
        :param quantization: as in `compute_portfolio()`
        :param reindex_like_input: as in `compute_portfolio()`
        :param burn_in_bars: as in `compute_portfolio()`
        :return: multiindexed dataframe with level-0 columns
            "returns", "volatility", "prediction", "position", "pnl"
        """
        holdings, position, flow, pnl, statistics_df = self.compute_portfolio(
            df,
            **kwargs,
        )
        portfolio_df = ForecastEvaluatorFromPrices._build_multiindex_df(
            df[self._price_col],
            df[self._volatility_col],
            df[self._prediction_col],
            holdings,
            position,
            flow,
            pnl,
        )
        return portfolio_df, statistics_df

    def get_cols(self) -> List[str]:
        """
        Return the names of the price, volatility, and prediction columns.
        """
        cols = [
            self._price_col,
            self._volatility_col,
            self._prediction_col,
        ]
        return cols

    def compute_counts(self, df: pd.DataFrame) -> pd.DataFrame:
        self._validate_df(df)

        def _compute_counts(df: pd.DataFrame, col: str) -> pd.DataFrame:
            return df[col].groupby(lambda x: x.time()).count()

        dfs = {
            "price_count": _compute_counts(df, self._price_col),
            "volatility_count": _compute_counts(df, self._volatility_col),
            "prediction_count": _compute_counts(df, self._prediction_col),
        }
        count_df = pd.concat(dfs.values(), axis=1, keys=dfs.keys())
        return count_df

    @staticmethod
    def _build_multiindex_df(
        price: pd.DataFrame,
        volatility: pd.DataFrame,
        prediction: pd.DataFrame,
        holdings: pd.DataFrame,
        position: pd.DataFrame,
        flow: pd.DataFrame,
        pnl: pd.DataFrame,
    ) -> pd.DataFrame:
        dfs = {
            "price": price,
            "volatility": volatility,
            "prediction": prediction,
            "holdings": holdings,
            "position": position,
            "flow": flow,
            "pnl": pnl,
        }
        portfolio_df = pd.concat(dfs.values(), axis=1, keys=dfs.keys())
        return portfolio_df

    @staticmethod
    def _cast_cols_to_int(
        df: pd.DataFrame,
    ) -> None:
        # If integers are converted to floats and then strings, then upon
        # being read they must be cast to floats before being cast to ints.
        df.columns = df.columns.astype("float64").astype("int64")

    @staticmethod
    def _write_df(
        df: pd.DataFrame,
        log_dir: str,
        name: str,
        file_name: str,
    ) -> None:
        path = os.path.join(log_dir, name, file_name)
        hio.create_enclosing_dir(path, incremental=True)
        df.to_csv(path)

    @staticmethod
    def _read_df(
        log_dir: str,
        name: str,
        file_name: str,
        tz: str,
    ) -> pd.DataFrame:
        path = os.path.join(log_dir, name, file_name)
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = df.index.tz_convert(tz)
        return df

    @staticmethod
    def _compute_target_positions_from_forecasts(
        volatility: pd.DataFrame,
        predictions: pd.DataFrame,
        bulk_frac_to_remove: float,
        bulk_fill_method: str,
        target_gmv: Union[float, pd.Series],
    ) -> pd.DataFrame:
        """
        Compute target dollar positions based on forecasts, basic constraints.
        """
        if predictions.columns.size > 1:
            gaussian_ranked = sigproc.gaussian_rank(
                predictions,
                bulk_frac_to_remove=bulk_frac_to_remove,
                bulk_fill_method=bulk_fill_method,
            )
        else:
            _LOG.info(
                "Predictions provided for one asset; skipping Gaussian ranking."
            )
            gaussian_ranked = predictions
        _LOG.debug(
            "gaussian_ranked=\n%s",
            hpandas.df_to_str(gaussian_ranked, num_rows=10),
        )
        target_position_signs = np.sign(gaussian_ranked)
        _LOG.debug(
            "target_position_signs=\n%s",
            hpandas.df_to_str(target_position_signs, num_rows=10),
        )
        target_positions = target_position_signs.divide(volatility ** 2)
        _LOG.debug(
            "target_positions=\n%s",
            hpandas.df_to_str(target_positions, num_rows=10),
        )
        target_positions = ForecastEvaluatorFromPrices._apply_gmv_scaling(
            target_positions, target_gmv
        )
        return target_positions

    @staticmethod
    def _apply_gmv_scaling(
        target_positions: pd.DataFrame,
        target_gmv: Optional[Union[float, pd.Series]],
    ) -> pd.DataFrame:
        if target_gmv is None:
            pass
        elif isinstance(target_gmv, float):
            if target_gmv > 0:
                l1_norm = target_positions.abs().sum(axis=1, min_count=1)
                scale_factor = l1_norm / target_gmv
                _LOG.debug(
                    "scale factor=\n%s",
                    hpandas.df_to_str(scale_factor, num_rows=None),
                )
                target_positions = target_positions.divide(scale_factor, axis=0)
            else:
                target_positions *= 0
            _LOG.debug(
                "gmv scaled target_positions=\n%s",
                hpandas.df_to_str(target_positions, num_rows=None),
            )
        elif isinstance(target_gmv, pd.Series):
            hdbg.dassert_lte(0, target_gmv.min())
            active_times = cofinanc.infer_active_times(target_positions)
            hdbg.dassert(
                active_times.difference(target_gmv.index).empty,
                "No `target_gmv` available at times=%s",
                active_times.difference(target_gmv.index),
            )
            new_target_positions = []
            for time, df in target_positions.groupby(lambda x: x.time()):
                df = ForecastEvaluatorFromPrices._apply_gmv_scaling(
                    df, target_gmv.loc[time]
                )
                new_target_positions.append(df)
            target_positions = pd.concat(new_target_positions).sort_index()
        else:
            raise ValueError(
                "`target_gmv` type=%s not supported", type(target_gmv)
            )
        return target_positions

    @staticmethod
    def _apply_quantization(
        holdings: pd.DataFrame,
        quantization: str,
    ) -> pd.DataFrame:
        if quantization == "no_quantization":
            pass
        elif quantization == "nearest_share":
            holdings = np.rint(holdings)
        elif quantization == "nearest_lot":
            holdings = 100 * np.rint(holdings / 100)
        else:
            raise ValueError(f"Invalid quantization strategy `{quantization}`")
        return holdings

    @staticmethod
    def _compute_statistics(
        positions: pd.DataFrame,
        flows: pd.DataFrame,
        pnl: pd.DataFrame,
    ) -> pd.DataFrame:
        # Gross market value (gross exposure).
        gmv = positions.abs().sum(axis=1, min_count=1)
        # Net market value (net asset value or net exposure).
        nmv = positions.sum(axis=1, min_count=1)
        # This is an approximation that does not take into account returns.
        traded_volume = -1 * flows
        # Absolute volume traded.
        gross_volume = flows.abs().sum(axis=1, min_count=1)
        # Net volume traded.
        net_volume = traded_volume.sum(axis=1, min_count=1)
        # Aggregated PnL.
        portfolio_pnl = pnl.sum(axis=1, min_count=1)
        stats = pd.DataFrame(
            {
                "pnl": portfolio_pnl,
                "gross_volume": gross_volume,
                "net_volume": net_volume,
                "gmv": gmv,
                "nmv": nmv,
            }
        )
        return stats

    @staticmethod
    def _get_df(df: pd.DataFrame, col: str) -> pd.DataFrame:
        hdbg.dassert_in(col, df.columns)
        return df[col]

    def _validate_df(self, df: pd.DataFrame) -> None:
        hpandas.dassert_time_indexed_df(
            df, allow_empty=True, strictly_increasing=True
        )
        hdbg.dassert_eq(df.columns.nlevels, 2)
        hdbg.dassert_is_subset(
            [self._price_col, self._volatility_col, self._prediction_col],
            df.columns.levels[0].to_list(),
        )

    def _apply_trimming(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Trim `df` according to ATH, weekends, missing data.
        """
        # Restrict to required columns.
        df = df[[self._price_col, self._volatility_col, self._prediction_col]]
        active_index = cofinanc.infer_active_bars(df[self._price_col])
        # Drop rows with no prices (this is an approximate way to handle weekends,
        # market holidays, and shortened trading sessions).
        df = df.reindex(index=active_index)
        return df

    def _compute_holdings_and_flows(
        self,
        price: pd.DataFrame,
        target_positions: pd.DataFrame,
        quantization: str,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Compute holdings in shares from price and dollar position targets.
        """
        # Compute target holdings based on prices available now.
        target_holdings = target_positions.divide(price)
        # Quantize.
        target_holdings = ForecastEvaluatorFromPrices._apply_quantization(
            target_holdings, quantization
        )
        # Assume target shares are obtained.
        holdings = target_holdings.shift(1)
        # TODO(Paul): Give the user the option of supplying the share
        # adjustment factors. Infer as below if they are not supplied.
        split_factors = cofinanc.infer_splits(price)
        timestamps = pd.DataFrame(
            price.index.to_list(), price.index, ["timestamp"]
        )
        bod_timestamps = timestamps.groupby(lambda x: x.date()).min()
        holdings.loc[bod_timestamps["timestamp"]] = np.nan
        holdings = holdings.ffill()
        splits = split_factors.merge(
            bod_timestamps, left_index=True, right_index=True
        ).set_index("timestamp")
        holdings = holdings.multiply(splits, fill_value=1)
        # Change in shares priced at end of bar. Only valid intraday.
        flows = -1 * holdings.subtract(holdings.shift(1), fill_value=0).multiply(
            price
        )
        # Set the overnight flow to zero (since we do not trade and since
        # the share count may change due to corporate actions).
        return holdings, flows
