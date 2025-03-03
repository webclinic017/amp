"""
Import as:

import helpers.hpandas as hpandas
"""
import logging
import random
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

import helpers.hdatetime as hdateti
import helpers.hdbg as hdbg
import helpers.hprint as hprint

# Avoid the following dependency from other `helpers` modules to prevent import cycles.
# import helpers.hs3 as hs3
# import helpers.hsql as hsql
# import helpers.hunit_test as hunitest


_LOG = logging.getLogger(__name__)


_LOG.verb_debug = hprint.install_log_verb_debug(_LOG, verbose=False)


# #############################################################################


def to_series(df: pd.DataFrame) -> pd.Series:
    """
    Convert a pd.DataFrame with a single column into a pd.Series.

    The problem is that empty df or df with a single row are not
    converted correctly to a pd.Series.
    """
    # See https://stackoverflow.com/questions/33246771
    hdbg.dassert_isinstance(df, pd.DataFrame)
    hdbg.dassert_eq(df.shape[1], 1, "df=%s doesn't have a single column", df)
    if df.empty:
        srs = pd.Series()
    elif df.shape[0] > 1:
        srs = df.squeeze()
    else:
        srs = pd.Series(df.iloc[0, 0], index=[df.index.values[0]])
        srs.name = df.index.name
    hdbg.dassert_isinstance(srs, pd.Series)
    return srs


def dassert_is_days(
    timedelta: pd.Timedelta, *, min_num_days: Optional[int] = None
) -> None:
    hdbg.dassert(
        (timedelta / pd.Timedelta(days=1)).is_integer(),
        "timedelta='%s' is not an integer number of days",
        timedelta,
    )
    if min_num_days is not None:
        hdbg.dassert_lte(1, timedelta.days)


# #############################################################################


def _get_index(obj: Union[pd.Index, pd.DataFrame, pd.Series]) -> pd.Index:
    """
    Return the index of a Pandas object.
    """
    if isinstance(obj, pd.Index):
        index = obj
    else:
        hdbg.dassert_isinstance(obj, (pd.Series, pd.DataFrame))
        index = obj.index
    return index


# TODO(gp): Maybe for symmetry with the other functions, rename to
#  dassert_datetime_index
def dassert_index_is_datetime(
    obj: Union[pd.Index, pd.DataFrame, pd.Series],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that the dataframe has an index containing datetimes.
    """
    index = _get_index(obj)
    hdbg.dassert_isinstance(index, pd.DatetimeIndex, msg, *args)


def dassert_unique_index(
    obj: Union[pd.Index, pd.DataFrame, pd.Series],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that a Pandas object has a unique index.
    """
    index = _get_index(obj)
    if not index.is_unique:
        dup_indices = index.duplicated(keep=False)
        df_dup = obj[dup_indices]
        dup_msg = f"Duplicated rows are:\n{df_to_str(df_dup)}\n"
        if msg is None:
            msg = dup_msg
        else:
            msg = dup_msg + msg
        hdbg.dassert(index.is_unique, msg=msg, *args)


# TODO(gp): @all Add unit tests.
def dassert_increasing_index(
    obj: Union[pd.Index, pd.DataFrame, pd.Series],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that a Pandas object has an increasing index.
    """
    index = _get_index(obj)
    if not index.is_monotonic_increasing:
        # Print information about the problematic indices like:
        # ```
        # Not increasing indices are:
        #                                  full_symbol         open         high
        # timestamp
        # 2018-08-17 01:39:00+00:00  binance::BTC_USDT  6339.250000  6348.910000
        # 2018-08-17 00:01:00+00:00   kucoin::ETH_USDT   286.712987   286.712987
        # ```
        # Find the problematic indices.
        mask = np.diff(index) <= pd.Timedelta(seconds=0)
        mask = np.insert(mask, 0, False)
        # TODO(gp): We might want to specify an integer with how many rows before
        #  after we want to show.
        # Shift back to get the previous index that was creating the issue.
        mask_shift = np.empty_like(mask)
        mask_shift[: len(mask) - 1] = mask[1 : len(mask)]
        mask_shift[len(mask) - 1] = False
        #
        mask = mask | mask_shift
        dup_msg = f"Not increasing indices are:\n{df_to_str(obj[mask])}\n"
        if msg is None:
            msg = dup_msg
        else:
            msg = dup_msg + msg
        # Dump the data to file for further inspection.
        # obj.to_csv("index.csv")
        hdbg.dassert(index.is_monotonic_increasing, msg=msg, *args)


# TODO(gp): @all Add more info in case of failures and unit tests.
def dassert_strictly_increasing_index(
    obj: Union[pd.Index, pd.DataFrame, pd.Series],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that a Pandas object has a strictly increasing index.
    """
    dassert_unique_index(obj, msg, *args)
    dassert_increasing_index(obj, msg, *args)


# TODO(gp): Not sure it's used or useful?
def dassert_monotonic_index(
    obj: Union[pd.Index, pd.DataFrame, pd.Series],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that a Pandas object has a monotonic (i.e., strictly increasing or
    decreasing index).
    """
    dassert_unique_index(obj, msg, *args)
    index = _get_index(obj)
    cond = index.is_monotonic_increasing or index.is_monotonic_decreasing
    hdbg.dassert(cond, msg=msg, *args)


# TODO(Paul): @gp -> dassert_datetime_indexed_df
def dassert_time_indexed_df(
    df: pd.DataFrame, allow_empty: bool, strictly_increasing: bool
) -> None:
    """
    Validate that input dataframe is time indexed and well-formed.

    :param df: dataframe to validate
    :param allow_empty: allow empty data frames
    :param strictly_increasing: if True the index needs to be strictly increasing,
      instead of just increasing
    """
    # Verify that Pandas dataframe is passed as input.
    hdbg.dassert_isinstance(df, pd.DataFrame)
    if not allow_empty:
        # Verify that a non-empty dataframe is passed as input.
        hdbg.dassert_lt(0, df.shape[0])
        # Verify that the dataframe has at least 1 column.
        hdbg.dassert_lte(1, len(df.columns))
    # Verify that the index is increasing.
    if strictly_increasing:
        dassert_strictly_increasing_index(df)
    else:
        dassert_increasing_index(df)
    # Check that the index is in datetime format.
    dassert_index_is_datetime(df)
    # Check that the passed timestamp has timezone info.
    hdateti.dassert_has_tz(df.index[0])


def dassert_valid_remap(to_remap: List[str], remap_dict: Dict[str, str]) -> None:
    """
    Ensure that remapping rows / columns is valid.
    """
    hdbg.dassert_isinstance(to_remap, list)
    hdbg.dassert_isinstance(remap_dict, dict)
    # All the rows / columns to remap, should exist.
    hdbg.dassert_is_subset(
        remap_dict.keys(),
        to_remap,
        "Keys to remap should be a subset of existing columns",
    )
    # The mapping is invertible.
    hdbg.dassert_no_duplicates(remap_dict.keys())
    hdbg.dassert_no_duplicates(remap_dict.values())
    # Rows / columns should not be remapped on existing rows / columns.
    hdbg.dassert_not_intersection(remap_dict.values(), to_remap)


def dassert_series_type_is(
    srs: pd.Series,
    type_: type,
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that the data type of `srs` is `type_`.

    Examples of valid series types are
      - np.float64
      - np.int64
      - pd.Timestamp
    """
    hdbg.dassert_isinstance(srs, pd.Series)
    hdbg.dassert_isinstance(type_, type)
    hdbg.dassert_eq(srs.dtype.type, type_, msg, *args)


def dassert_series_type_in(
    srs: pd.Series,
    types: List[type],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that the data type of `srs` is one of the types in `types`.
    """
    hdbg.dassert_isinstance(srs, pd.Series)
    hdbg.dassert_container_type(types, list, type)
    hdbg.dassert_in(srs.dtype.type, types, msg, *args)


# #############################################################################


def resample_index(index: pd.DatetimeIndex, frequency: str) -> pd.DatetimeIndex:
    """
    Resample `DatetimeIndex`.

    :param index: `DatetimeIndex` to resample
    :param frequency: frequency from `pd.date_range()` to resample to
    :return: resampled `DatetimeIndex`
    """
    _LOG.debug(hprint.to_str("index frequency"))
    hdbg.dassert_isinstance(index, pd.DatetimeIndex)
    dassert_unique_index(index, msg="Index must have only unique values")
    min_date = index.min()
    max_date = index.max()
    _LOG.debug("min_date=%s max_date=%s", min_date, max_date)
    # TODO(gp): Preserve the index name.
    # index_name = index.name
    resampled_index = pd.date_range(
        start=min_date,
        end=max_date,
        freq=frequency,
    )
    # Enable detailed debugging.
    if False:
        if len(resampled_index) > len(index):
            # Downsample.
            _LOG.debug(
                "Index length increased by %s = %s - %s",
                len(resampled_index) - len(index),
                len(resampled_index),
                len(index),
            )
        elif len(resampled_index) < len(index):
            # Upsample.
            _LOG.debug(
                "Index length decreased by %s = %s - %s",
                len(index) - len(resampled_index),
                len(index),
                len(resampled_index),
            )
        else:
            _LOG.debug("Index length=%s has not changed", len(index))
    # resampled_index.name = index_name
    return resampled_index


def resample_df(df: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """
    Resample `DataFrame` by placing NaN in missing locations in the index.

    :param df: `DataFrame` to resample
    :param frequency: frequency from `pd.date_range()` to resample to
    :return: resampled `DataFrame`
    """
    hdbg.dassert_isinstance(df, pd.DataFrame)
    # Preserve the index name.
    index_name = df.index.name
    resampled_index = resample_index(df.index, frequency)
    df_reindex = df.reindex(resampled_index)
    df_reindex.index.name = index_name
    return df_reindex


def find_gaps_in_dataframes(
    df1: pd.DataFrame, df2: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Find data present in one dataframe and missing in the other one.

    :param df1: first dataframe for comparison
    :param df2: second dataframe for comparison
    :return: two dataframes with missing data
    """
    # Get data present in first, but not present in second dataframe.
    first_missing_indices = df2.index.difference(df1.index)
    first_missing_data = df2.loc[first_missing_indices]
    # Get data present in second, but not present in first dataframe.
    second_missing_indices = df1.index.difference(df2.index)
    second_missing_data = df1.loc[second_missing_indices]
    return first_missing_data, second_missing_data


def compare_dataframe_rows(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    """
    Compare contents of rows with same indices.

    Index is set to default sequential integer values because compare is
    sensitive to multi index (probably because new multi indexes are created
    for each difference in `compare`). Multi index columns are regular columns now.
    Excess columns are removed so both dataframes are always same shape because
    `compare` expects identical dataframes (same number of rows, columns, etc.).

    :param df1: first dataframe for comparison
    :param df2: second dataframe for comparison
    :return: dataframe with data with same indices and different contents
    """
    # Get rows on which the two dataframe indices match.
    idx_intersection = df1.index.intersection(df2.index)
    # Remove excess columns and reset indexes.
    trimmed_second = df2.loc[idx_intersection].reset_index()
    trimmed_first = df1.loc[idx_intersection].reset_index()
    # Get difference between second and first dataframe.
    data_difference = trimmed_second.compare(trimmed_first)
    # Update data difference with original dataframe index names
    # for easier identification.
    index_names = tuple(df2.index.names)
    # If index or multi index is named, it will be visible in data difference.
    if index_names != (None,):
        for index in data_difference.index:
            for column in index_names:
                data_difference.loc[index, column] = trimmed_second.loc[index][
                    column
                ]
        data_difference = data_difference.convert_dtypes()
    return data_difference


def drop_duplicates(
    data: Union[pd.Series, pd.DataFrame],
    *args: Any,
    **kwargs: Any,
) -> Union[pd.Series, pd.DataFrame]:
    """
    Create a wrapper around `pandas.drop_duplicates()`.

    See the official docs:
    - https://pandas.pydata.org/docs/reference/api/pandas.Series.drop_duplicates.html
    - https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop_duplicates.html

    :return: data without duplicates
    """
    _LOG.debug("args=%s, kwargs=%s", str(args), str(kwargs))
    num_rows_before = data.shape[0]
    # Drop duplicates.
    data_no_dups = data.drop_duplicates(*args, **kwargs)
    # Report change.
    num_rows_after = data_no_dups.shape[0]
    if num_rows_before != num_rows_after:
        _LOG.debug(
            "Removed %s rows",
            hprint.perc(num_rows_before - num_rows_after, num_rows_before),
        )
    return data_no_dups


def dropna(
    df: pd.DataFrame,
    drop_infs: bool = False,
    report_stats: bool = False,
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Create a wrapper around pd.dropna() reporting information about the removed
    rows.

    :param df: dataframe to process
    :param drop_infs: if +/- np.inf should be considered as nans
    :param report_stats: if processing stats should be reported
    :return: dataframe with nans dropped
    """
    hdbg.dassert_isinstance(df, pd.DataFrame)
    num_rows_before = df.shape[0]
    if drop_infs:
        df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(*args, **kwargs)
    if report_stats:
        num_rows_after = df.shape[0]
        pct_removed = hprint.perc(
            num_rows_before - num_rows_after, num_rows_before
        )
        _LOG.info("removed rows with nans: %s", pct_removed)
    return df


def drop_axis_with_all_nans(
    df: pd.DataFrame,
    drop_rows: bool = True,
    drop_columns: bool = False,
    drop_infs: bool = False,
    report_stats: bool = False,
) -> pd.DataFrame:
    """
    Remove columns and rows not containing information (e.g., with only nans).

    The operation is not performed in place and the resulting df is returned.
    Assume that the index is timestamps.

    :param df: dataframe to process
    :param drop_rows: remove rows with only nans
    :param drop_columns: remove columns with only nans
    :param drop_infs: remove also +/- np.inf
    :param report_stats: report the stats of the operations
    :return: dataframe with specific nan axis dropped
    """
    hdbg.dassert_isinstance(df, pd.DataFrame)
    if drop_infs:
        df = df.replace([np.inf, -np.inf], np.nan)
    if drop_columns:
        # Remove columns with all nans, if any.
        cols_before = df.columns[:]
        df = df.dropna(axis=1, how="all")
        if report_stats:
            # Report results.
            cols_after = df.columns[:]
            removed_cols = set(cols_before).difference(set(cols_after))
            pct_removed = hprint.perc(
                len(cols_before) - len(cols_after), len(cols_after)
            )
            _LOG.info(
                "removed cols with all nans: %s %s",
                pct_removed,
                hprint.list_to_str(removed_cols),
            )
    if drop_rows:
        # Remove rows with all nans, if any.
        rows_before = df.index[:]
        df = df.dropna(axis=0, how="all")
        if report_stats:
            # Report results.
            rows_after = df.index[:]
            removed_rows = set(rows_before).difference(set(rows_after))
            if len(rows_before) == len(rows_after):
                # Nothing was removed.
                min_ts = max_ts = None
            else:
                # TODO(gp): Report as intervals of dates.
                min_ts = min(removed_rows)
                max_ts = max(removed_rows)
            pct_removed = hprint.perc(
                len(rows_before) - len(rows_after), len(rows_after)
            )
            _LOG.info(
                "removed rows with all nans: %s [%s, %s]",
                pct_removed,
                min_ts,
                max_ts,
            )
    return df


def reindex_on_unix_epoch(
    df: pd.DataFrame, in_col_name: str, unit: str = "s"
) -> pd.DataFrame:
    """
    Transform the column `in_col_name` into a datetime index. `in_col_name`
    contains Unix epoch (e.g., 1638194400) and it is converted into a UTC time.

    :param df: dataframe with a unix epoch
    :param in_col_name: column containing unix epoch
    :param unit: the unit of unix epoch
    """
    # Convert.
    temp_col_name = in_col_name + "_tmp"
    hdbg.dassert_in(in_col_name, df.columns)
    hdbg.dassert_not_in(temp_col_name, df.columns)
    # Save.
    df[temp_col_name] = pd.to_datetime(df[in_col_name], unit=unit, utc=True)
    df.set_index(temp_col_name, inplace=True, drop=True)
    df.index.name = None
    return df


def get_df_signature(df: pd.DataFrame, num_rows: int = 6) -> str:
    """
    Compute a simple signature of a dataframe in string format.

    The signature contains metadata about dataframe size and certain
    amount of rows from start and end of a dataframe. It is used for
    testing purposes.
    """
    hdbg.dassert_isinstance(df, pd.DataFrame)
    text: List[str] = [f"df.shape={str(df.shape)}"]
    with pd.option_context(
        "display.max_colwidth", int(1e6), "display.max_columns", None
    ):
        # If dataframe size exceeds number of rows, show only subset in form of
        # first and last rows. Otherwise, whole dataframe is shown.
        if len(df) > num_rows:
            text.append(f"df.head=\n{df.head(num_rows // 2)}")
            text.append(f"df.tail=\n{df.tail(num_rows // 2)}")
        else:
            text.append(f"df.full=\n{df}")
    text: str = "\n".join(text)
    return text


# #############################################################################


def trim_df(
    df: pd.DataFrame,
    ts_col_name: Optional[str],
    start_ts: Optional[pd.Timestamp],
    end_ts: Optional[pd.Timestamp],
    left_close: bool,
    right_close: bool,
) -> pd.DataFrame:
    """
    Trim df using values in `ts_col_name` in interval bounded by `start_ts` and
    `end_ts`.

    :param ts_col_name: the name of the column. `None` means index
    :param start_ts, end_ts: boundaries of the desired interval
    :param left_close, right_close: encode what to do with the boundaries of the
        interval
        - E.g., [start_ts, end_ts), or (start_ts, end_ts]
    """
    _LOG.verb_debug(
        df_to_str(df, print_dtypes=True, print_shape_info=True, tag="df")
    )
    _LOG.debug(
        hprint.to_str("ts_col_name start_ts end_ts left_close right_close")
    )
    if df.empty:
        # If the df is empty there is nothing to trim.
        return df
    num_rows_before = df.shape[0]
    if start_ts is not None and end_ts is not None:
        hdateti.dassert_tz_compatible(start_ts, end_ts)
        hdbg.dassert_lte(start_ts, end_ts)
    # Handle the index.
    use_index = False
    if ts_col_name is None:
        # Convert the index into a regular column.
        # TODO(gp): Use binary search if there is an index.
        if df.index.name is None:
            _LOG.debug(
                "The df has no index\n%s",
                df_to_str(df.head()),
            )
            df.index.name = "index"
        ts_col_name = df.index.name
        df = df.reset_index()
        use_index = True
    # TODO(gp): This is inefficient. Make it faster by binary search, if ordered.
    hdbg.dassert_in(ts_col_name, df.columns)
    # Filter based on start_ts.
    _LOG.debug("Filtering by start_ts=%s", start_ts)
    if start_ts is not None:
        _LOG.verb_debug("start_ts=%s", start_ts)
        # Convert the column into `pd.Timestamp` to compare it to `start_ts`.
        # This is needed to sidestep the comparison hell involving `numpy.datetime64`
        # vs Pandas objects.
        tss = pd.to_datetime(df[ts_col_name])
        hdateti.dassert_tz_compatible(tss.iloc[0], start_ts)
        _LOG.verb_debug("tss=\n%s", df_to_str(tss))
        if left_close:
            mask = tss >= start_ts
        else:
            mask = tss > start_ts
        _LOG.verb_debug("mask=\n%s", df_to_str(mask))
        df = df[mask]
    # Filter based on end_ts.
    _LOG.debug("Filtering by end_ts=%s", end_ts)
    if not df.empty:
        if end_ts is not None:
            _LOG.debug("Filtering by start_ts=%s", start_ts)
            _LOG.verb_debug("end_ts=%s", end_ts)
            tss = pd.to_datetime(df[ts_col_name])
            hdateti.dassert_tz_compatible(tss.iloc[0], end_ts)
            _LOG.verb_debug("tss=\n%s", df_to_str(tss))
            if right_close:
                mask = tss <= end_ts
            else:
                mask = tss < end_ts
            _LOG.verb_debug("mask=\n%s", df_to_str(mask))
            df = df[mask]
    else:
        # If the df is empty there is nothing to trim.
        pass
    if use_index:
        df = df.set_index(ts_col_name, drop=True)
    # Report the changes.
    num_rows_after = df.shape[0]
    if num_rows_before != num_rows_after:
        _LOG.debug(
            "Removed %s rows",
            hprint.perc(num_rows_before - num_rows_after, num_rows_before),
        )
    return df


# #############################################################################


def _df_to_str(
    df: pd.DataFrame,
    *,
    num_rows: Optional[int] = 6,
    max_columns: int = 10000,
    max_colwidth: int = 2000,
    max_rows: int = 500,
    precision: int = 6,
    display_width: int = 10000,
    use_tabulate: bool = False,
) -> str:
    out = []
    # Set dataframe print options.
    with pd.option_context(
        "display.max_colwidth",
        max_colwidth,
        # "display.height", 1000,
        "display.max_rows",
        max_rows,
        "display.precision",
        precision,
        "display.max_columns",
        max_columns,
        "display.width",
        display_width,
    ):
        if use_tabulate:
            import tabulate

            out.append(tabulate.tabulate(df, headers="keys", tablefmt="psql"))
        if num_rows is None or df.shape[0] <= num_rows:
            # Print the entire data frame.
            out.append(str(df))
        else:
            # Print top and bottom of df.
            out.append(str(df.head(num_rows // 2)))
            out.append("...")
            tail_str = str(df.tail(num_rows // 2))
            # Remove index and columns.
            skipped_rows = 1
            if df.index.name:
                skipped_rows += 1
            tail_str = "\n".join(tail_str.split("\n")[skipped_rows:])
            out.append(tail_str)
    txt = "\n".join(out)
    return txt


def df_to_str(
    df: Union[pd.DataFrame, pd.Series, pd.Index],
    *,
    num_rows: Optional[int] = 6,
    print_dtypes: bool = False,
    print_shape_info: bool = False,
    print_nan_info: bool = False,
    print_memory_usage: bool = False,
    memory_usage_mode: str = "human_readable",
    tag: Optional[str] = None,
    max_columns: int = 10000,
    max_colwidth: int = 2000,
    max_rows: int = 500,
    precision: int = 6,
    display_width: int = 10000,
    use_tabulate: bool = False,
) -> str:
    """
    Print a dataframe to string reporting all the columns without trimming.

    :param: num_rows: max number of rows to print (half from the top and half from
        the bottom of the dataframe)
        - `None` to print the entire dataframe
    :param print_dtypes: report dataframe types and information about the type of
        each column by looking at the first value
    :param print_shape_info: report dataframe shape, index and columns
    :param print_memory_usage: report memory use for each
    """
    if df is None:
        return ""
    if isinstance(df, pd.Series):
        df = pd.DataFrame(df)
    elif isinstance(df, pd.Index):
        df = df.to_frame(index=False)
    hdbg.dassert_isinstance(df, pd.DataFrame)
    out = []
    # Print the tag.
    if tag is not None:
        out.append(f"# {tag}=")
    if not df.empty:
        # Print information about the shape and index.
        # TODO(Nikola): Revisit and rename print_shape_info to print_axes_info
        if print_shape_info:
            # TODO(gp): Unfortunately we can't improve this part of the output
            # since there are many golden inside the code that would need to be
            # updated. Consider automating updating the expected values in the code.
            txt = f"index=[{df.index.min()}, {df.index.max()}]"
            out.append(txt)
            txt = f"columns={','.join(map(str, df.columns))}"
            out.append(txt)
            txt = f"shape={str(df.shape)}"
            out.append(txt)
        # Print information about the types.
        if print_dtypes:
            out.append("* type=")

            table = []

            def _report_srs_stats(srs: pd.Series) -> List[Any]:
                """
                Report dtype, the first element, and its type of series.
                """
                row: List[Any] = []
                first_elem = srs.values[0]
                num_unique = srs.nunique()
                num_nans = srs.isna().sum()
                row.extend(
                    [
                        srs.dtype,
                        hprint.perc(num_unique, len(srs)),
                        hprint.perc(num_nans, len(srs)),
                        first_elem,
                        type(first_elem),
                    ]
                )
                return row

            row = []
            col_name = "index"
            row.append(col_name)
            row.extend(_report_srs_stats(df.index))
            row = map(str, row)
            table.append(row)
            for col_name in df.columns:
                row_: List[Any] = []
                row_.append(col_name)
                row_.extend(_report_srs_stats(df[col_name]))
                row_ = map(str, row_)
                table.append(row_)
            #
            columns = [
                "col_name",
                "dtype",
                "num_unique",
                "num_nans",
                "first_elem",
                "type(first_elem)",
            ]
            df_stats = pd.DataFrame(table, columns=columns)
            df_stats_as_str = _df_to_str(df_stats, num_rows=None)
            out.append(df_stats_as_str)
        # Print info about memory usage.
        if print_memory_usage:
            out.append("* memory=")
            mem_use_df = pd.concat(
                [df.memory_usage(deep=False), df.memory_usage(deep=True)], axis=1
            )
            mem_use_df.columns = ["shallow", "deep"]
            # Add total row.
            mem_use_df_total = mem_use_df.sum(axis=0)
            mem_use_df_total.name = "Total"
            mem_use_df = mem_use_df.append(mem_use_df_total.T)
            # Convert into the desired format.
            if memory_usage_mode == "bytes":
                pass
            elif memory_usage_mode == "human_readable":
                import helpers.hintrospection as hintros

                mem_use_df = mem_use_df.applymap(hintros.format_size)
            else:
                raise ValueError(
                    f"Invalid memory_usage_mode='{memory_usage_mode}'"
                )
            memory_usage_as_txt = _df_to_str(mem_use_df, num_rows=None)
            out.append(memory_usage_as_txt)
        # Print info about nans.
        if print_nan_info:
            num_elems = df.shape[0] * df.shape[1]
            num_nans = df.isna().sum().sum()
            txt = f"num_nans={hprint.perc(num_nans, num_elems)}"
            out.append(txt)
            #
            num_zeros = df.isnull().sum().sum()
            txt = f"num_zeros={hprint.perc(num_zeros, num_elems)}"
            out.append(txt)
            # TODO(gp): np can't do isinf on objects like strings.
            # num_infinite = np.isinf(df).sum().sum()
            # txt = "num_infinite=%s" % hprint.perc(num_infinite, num_elems)
            # out.append(txt)
            #
            num_nan_rows = df.dropna().shape[0]
            txt = f"num_nan_rows={hprint.perc(num_nan_rows, num_elems)}"
            out.append(txt)
            #
            num_nan_cols = df.dropna(axis=1).shape[1]
            txt = f"num_nan_cols={hprint.perc(num_nan_cols, num_elems)}"
            out.append(txt)
    # Print the df.
    df_as_str = _df_to_str(
        df,
        num_rows=num_rows,
        max_columns=max_columns,
        max_colwidth=max_colwidth,
        max_rows=max_rows,
        precision=precision,
        display_width=display_width,
        use_tabulate=use_tabulate,
    )
    out.append(df_as_str)
    txt = "\n".join(out)
    return txt


def convert_df_to_json_string(
    df: pd.DataFrame,
    n_head: Optional[int] = 10,
    n_tail: Optional[int] = 10,
    columns_order: Optional[List[str]] = None,
) -> str:
    """
    Convert dataframe to pretty-printed JSON string.

    To select all rows of the dataframe, pass `n_head` as None.

    :param df: dataframe to convert
    :param n_head: number of printed top rows
    :param n_tail: number of printed bottom rows
    :param columns_order: order for the KG columns sort
    :return: dataframe converted to JSON string
    """
    # Append shape of the initial dataframe.
    shape = f"original shape={df.shape}"
    # Reorder columns.
    if columns_order is not None:
        hdbg.dassert_set_eq(columns_order, df.cols)
        df = df[columns_order]
    # Select head.
    if n_head is not None:
        head_df = df.head(n_head)
    else:
        # If no n_head provided, append entire dataframe.
        head_df = df
    # Transform head to json.
    head_json = head_df.to_json(
        orient="index",
        force_ascii=False,
        indent=4,
        default_handler=str,
        date_format="iso",
        date_unit="s",
    )
    if n_tail is not None:
        # Transform tail to json.
        tail = df.tail(n_tail)
        tail_json = tail.to_json(
            orient="index",
            force_ascii=False,
            indent=4,
            default_handler=str,
            date_format="iso",
            date_unit="s",
        )
    else:
        # If no tail specified, append an empty string.
        tail_json = ""
    # Join shape and dataframe to single string.
    output_str = "\n".join([shape, "Head:", head_json, "Tail:", tail_json])
    return output_str


# #############################################################################


def convert_col_to_int(
    df: pd.DataFrame,
    col: str,
) -> pd.DataFrame:
    """
    Convert a column to an integer column.

    Example use case: Parquet uses categoricals. If supplied with a
    categorical-type column, this function will convert it to an integer
    column.
    """
    hdbg.dassert_isinstance(df, pd.DataFrame)
    hdbg.dassert_isinstance(col, str)
    hdbg.dassert_in(col, df.columns)
    # Attempt the conversion.
    df[col] = df[col].astype("int64")
    # Trust, but verify.
    dassert_series_type_is(df[col], np.int64)
    return df


# #############################################################################


def read_csv_to_df(
    stream: Union[str, "s3fs.core.S3File", "s3fs.core.S3FileSystem"],
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Read a CSV file into a `pd.DataFrame`.
    """
    # Gets filename from stream if it is not already a string,
    # so it can be inspected for extension type.
    file_name = stream if isinstance(stream, str) else vars(stream)["path"]
    # Handle zipped files.
    if any(file_name.endswith(ext) for ext in (".gzip", ".gz", ".tgz")):
        hdbg.dassert_not_in("compression", kwargs)
        kwargs["compression"] = "gzip"
    elif file_name.endswith(".zip"):
        hdbg.dassert_not_in("compression", kwargs)
        kwargs["compression"] = "zip"
    # Read.
    _LOG.debug(hprint.to_str("args kwargs"))
    df = pd.read_csv(stream, *args, **kwargs)
    return df


def read_parquet_to_df(
    stream: Union[str, "s3fs.core.S3File", "s3fs.core.S3FileSystem"],
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Read a Parquet file into a `pd.DataFrame`.
    """
    # Read.
    _LOG.debug(hprint.to_str("args kwargs"))
    df = pd.read_parquet(stream, *args, **kwargs)
    return df


# #############################################################################


# TODO(Paul): Add unit tests.
def compute_weighted_sum(
    dfs: Dict[str, pd.DataFrame],
    weights: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Compute weighted sums of `dfs` using `weights`.

    :param dfs: dataframes keyed by id; all dfs should have the same index
        and cols
    :param weights: float weights indexed by id with unique col names
    :return: weighted sums keyed by weight col names
    """
    hdbg.dassert_isinstance(dfs, dict)
    hdbg.dassert(dfs, "dictionary of dfs must be nonempty")
    # Get a dataframe from the dictionary and record its index and columns.
    id_ = list(dfs)[0]
    hdbg.dassert_isinstance(id_, str)
    df = dfs[id_]
    hdbg.dassert_isinstance(df, pd.DataFrame)
    idx = df.index
    cols = df.columns
    # Sanity-check dataframes in dictionary.
    for key, value in dfs.items():
        hdbg.dassert_isinstance(key, str)
        hdbg.dassert_isinstance(value, pd.DataFrame)
        hdbg.dassert(
            value.index.equals(idx),
            "Index equality fails for keys=%s, %s",
            id_,
            key,
        )
        hdbg.dassert(
            value.columns.equals(cols),
            "Column equality fails for keys=%s, %s",
            id_,
            key,
        )
    # Sanity-check weights.
    hdbg.dassert_isinstance(weights, pd.DataFrame)
    hdbg.dassert_eq(weights.columns.nlevels, 1)
    hdbg.dassert(not weights.columns.has_duplicates)
    hdbg.dassert_set_eq(weights.index.to_list(), list(dfs))
    # Create a multiindexed dataframe to facilitate computing the weighted sums.
    weighted_dfs = {}
    combined_df = pd.concat(dfs.values(), axis=1, keys=dfs.keys())
    # TODO(Paul): Consider relaxing the NaN-handling.
    for col in weights.columns:
        weighted_combined_df = combined_df.multiply(weights[col], level=0)
        weighted_sums = weighted_combined_df.groupby(axis=1, level=1).sum(
            min_count=len(dfs)
        )
        weighted_dfs[col] = weighted_sums
    return weighted_dfs


def subset_df(df: pd.DataFrame, nrows: int, seed: int = 42) -> pd.DataFrame:
    """
    Remove N rows from the input data and shuffle the remaining ones.

    :param df: input data
    :param nrows: the number of rows to remove from the original data
    :param seed: see `random.seed()`
    :return: shuffled data with removed rows
    """
    hdbg.dassert_lte(1, nrows)
    hdbg.dassert_lte(nrows, df.shape[0])
    idx = list(range(df.shape[0]))
    random.seed(seed)
    random.shuffle(idx)
    idx = sorted(idx[nrows:])
    return df.iloc[idx]


def get_random_df(
    num_cols: int,
    seed: Optional[int] = None,
    date_range_kwargs: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Compute df with random data with `num_cols` columns and index obtained by
    calling `pd.date_range(**kwargs)`.

    :param num_cols: the number of columns in a DataFrame to generate
    :param seed: see `random.seed()`
    :param date_range_kwargs: kwargs for `pd.date_range()`
    """
    if seed:
        np.random.seed(seed)
    dt = pd.date_range(**date_range_kwargs)
    df = pd.DataFrame(np.random.rand(len(dt), num_cols), index=dt)
    return df
