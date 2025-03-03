"""
Import as:

import helpers.hdatetime as hdateti
"""

import asyncio
import calendar
import datetime
import logging
import re
from typing import Callable, Iterable, Optional, Tuple, Union, cast

# TODO(gp): Use hdbg.WARNING
_WARNING = "\033[33mWARNING\033[0m"


try:
    import dateutil.parser as dparse
except ModuleNotFoundError:
    _module = "dateutil"
    print(_WARNING + f": Can't find {_module}: continuing")

# Avoid dependency from other `helpers` modules to prevent import cycles.

import pandas as pd  # noqa: E402 # pylint: disable=wrong-import-position

# TODO(gp): Check if dateutils is equivalent to `pytz` or better so we can simplify
#  the dependencies.
try:
    import pytz
except ModuleNotFoundError:
    _module = "pytz"
    print(_WARNING + f": Can't find {_module}: continuing")


import helpers.hdbg as hdbg  # noqa: E402 # pylint: disable=wrong-import-position
import helpers.hprint as hprint  # noqa: E402 # pylint: disable=wrong-import-position

_LOG = logging.getLogger(__name__)

# We use the type `Datetime` to allow flexibility in the interface exposed to client.
# The typical pattern is:
# - we call `to_datetime()`, as soon as we enter functions exposed to users,
#   to convert the user-provided datetime into a `datetime.datetime`
# - we use only `datetime.datetime` in the private interfaces
# TODO(gp): In practice we are using `pd.Timestamp`
#
# It's often worth to import this file even for just the type `Datetime`,
# since typically as soon as the caller uses this type, they also want to use
# `to_datetime()` and `dassert_*()` functions.
# TODO(gp): It would be better to call this `GeneralDateTime`, `FlexibleDateTime`,
#  and rename `StrictDateTime` -> `DateTime`.
Datetime = Union[str, pd.Timestamp, datetime.datetime]

# The type `StrictDateTime` is for stricter interfaces, although it is a bit of a
# compromise.
# Either one wants to allow everything that can be interpreted as a datetime (and
# then use `Datetime`), or strict (and then use only `datetime.datetime`).
StrictDatetime = Union[pd.Timestamp, datetime.datetime]


def dassert_is_datetime(datetime_: Datetime) -> None:
    """
    Assert that `datetime_` is of type `Datetime`.
    """
    hdbg.dassert_isinstance(
        datetime_,
        (str, pd.Timestamp, datetime.datetime),
        "datetime_='%s' of type '%s' is not a DateTimeType",
        datetime_,
        str(type(datetime_)),
    )


def dassert_is_strict_datetime(datetime_: StrictDatetime) -> None:
    """
    Assert that `datetime_` is of type `StrictDatetime`.
    """
    hdbg.dassert_isinstance(
        datetime_,
        (pd.Timestamp, datetime.datetime),
        "datetime_='%s' of type '%s' is not a StrictDateTimeType",
        datetime_,
        str(type(datetime_)),
    )


# TODO(Grisha): also pass timezone.
def to_datetime(datetime_: Datetime) -> datetime.datetime:
    """
    Convert a `Datetime` into a `datetime.datetime`.

    :return: tz-aware or naive datetime.datetime
    """
    dassert_is_datetime(datetime_)
    if isinstance(datetime_, str):
        datetime_ = pd.Timestamp(datetime_)
    if isinstance(datetime_, pd.Timestamp):
        datetime_ = datetime_.to_pydatetime()
    return datetime_  # type: ignore


def to_timestamp(datetime_: Datetime) -> pd.Timestamp:
    """
    Convert a `Datetime` into a `pd.Timestamp`.

    :return: tz-aware or naive datetime.datetime
    """
    dassert_is_datetime(datetime_)
    timestamp = pd.Timestamp(datetime_)
    return timestamp


# //////////////////////////////////////////////////////////////////////////////////O


def dassert_is_tz_naive(datetime_: StrictDatetime) -> None:
    """
    Assert that the passed timestamp is tz-naive, i.e., doesn't have timezone
    info.
    """
    hdbg.dassert_is(
        datetime_.tzinfo, None, "datetime_='%s' is not tz naive", datetime_
    )


def dassert_has_tz(datetime_: StrictDatetime) -> None:
    """
    Assert that the passed timestamp has timezone info.
    """
    hdbg.dassert_is_not(
        datetime_.tzinfo,
        None,
        "datetime_='%s' doesn't have timezone info",
        datetime_,
    )


def dassert_has_specified_tz(
    datetime_: StrictDatetime, tz_zones: Iterable[str]
) -> None:
    """
    Assert that the passed timestamp has the timezone passed in `tz_zones`.
    """
    # Make sure that the passed timestamp has timezone information.
    dassert_has_tz(datetime_)
    # Get the timezone.
    tz_info = datetime_.tzinfo
    tz_zone = tz_info.zone  # type: ignore
    has_expected_tz = tz_zone in tz_zones
    hdbg.dassert(
        has_expected_tz,
        "datetime_=%s (type=%s) tz_info=%s tz_info.zone=%s instead of tz_zones=%s",
        datetime_,
        type(datetime_),
        tz_info,
        tz_zone,
        tz_zones,
    )


def dassert_has_UTC_tz(datetime_: StrictDatetime) -> None:
    """
    Assert that the passed timestamp is UTC.
    """
    tz_zones = (pytz.timezone("UTC").zone,)
    dassert_has_specified_tz(datetime_, tz_zones)


def dassert_has_ET_tz(datetime_: StrictDatetime) -> None:
    """
    Assert that the passed timestamp is Eastern Time (ET).
    """
    tz_zones = (
        pytz.timezone("US/Eastern").zone,
        pytz.timezone("America/New_York").zone,
    )
    dassert_has_specified_tz(datetime_, tz_zones)


def dassert_tz_compatible(
    datetime1: StrictDatetime, datetime2: StrictDatetime
) -> None:
    """
    Assert that two timestamps are both naive or both have timezone info.
    """
    dassert_is_strict_datetime(datetime1)
    dassert_is_strict_datetime(datetime2)
    has_tz1 = datetime1.tzinfo is not None
    has_tz2 = datetime2.tzinfo is not None
    hdbg.dassert_eq(
        has_tz1,
        has_tz2,
        "datetime1='%s' and datetime2='%s' are not compatible",
        str(datetime1),
        str(datetime2),
    )


# TODO(gp): Replace this check with compatibility between series vs scalar.
# def dassert_srs_tz_compatible(
# def dassert_srs_has_tz
# def dassert_srs_is_tz_naive
def dassert_tz_compatible_timestamp_with_df(
    datetime_: StrictDatetime,
    df: pd.DataFrame,
    col_name: Optional[str],
) -> None:
    """
    Assert that timestamp and a df column are both naive or both have timezone
    info.

    :param col_name: col_name. `None` represents the index.
    """
    dassert_is_strict_datetime(datetime_)
    hdbg.dassert_isinstance(df, pd.DataFrame)
    if df.empty:
        return
    if col_name is None:
        # We assume that the first element in the index is representative.
        df_datetime = df.index[0]
    else:
        hdbg.dassert_in(col_name, df.columns)
        df_datetime = df[col_name].iloc[0]
    dassert_tz_compatible(df_datetime, datetime_)


# //////////////////////////////////////////////////////////////////////////////////O


def dassert_is_valid_timestamp(timestamp: Optional[pd.Timestamp]) -> None:
    """
    Assert that a timestamp is `None` or a `pd.Timestamp` with timezone.
    """
    if timestamp is not None:
        hdbg.dassert_isinstance(timestamp, pd.Timestamp)
        dassert_has_tz(timestamp)


def dassert_timestamp_lte(
    start_timestamp: Optional[pd.Timestamp], end_timestamp: Optional[pd.Timestamp]
) -> None:
    dassert_is_valid_timestamp(start_timestamp)
    dassert_is_valid_timestamp(end_timestamp)
    if start_timestamp is not None and end_timestamp is not None:
        hdbg.dassert_lte(start_timestamp, end_timestamp)


def dassert_timestamp_lt(
    start_timestamp: Optional[pd.Timestamp], end_timestamp: Optional[pd.Timestamp]
) -> None:
    dassert_is_valid_timestamp(start_timestamp)
    dassert_is_valid_timestamp(end_timestamp)
    if start_timestamp is not None and end_timestamp is not None:
        hdbg.dassert_lt(start_timestamp, end_timestamp)


def dassert_is_valid_interval(
    start_timestamp: Optional[pd.Timestamp],
    end_timestamp: Optional[pd.Timestamp],
    left_close: bool,
    right_close: bool,
) -> None:
    """
    Assert that an interval has valid start and end timestamps.
    """
    _LOG.debug(
        hprint.to_str("start_timestamp end_timestamp left_close right_close")
    )
    dassert_is_valid_timestamp(start_timestamp)
    dassert_is_valid_timestamp(end_timestamp)
    # Check the requested interval.
    if start_timestamp is not None and end_timestamp is not None:
        if left_close and right_close:
            # If they are both closed, an interval like [a, a] makes sense,
            # otherwise it doesn't.
            hdbg.dassert_lte(start_timestamp, end_timestamp)
        else:
            hdbg.dassert_lt(start_timestamp, end_timestamp)


# #############################################################################


def get_UTC_tz() -> datetime.tzinfo:
    """
    Return the UTC timezone.
    """
    return pytz.timezone("UTC")


def get_ET_tz() -> datetime.tzinfo:
    """
    Return the US Eastern Time timezone.
    """
    # TODO(Grisha): -> `US/Eastern`?
    # It appears that "America/New_York" is to be preferred over "US/Eastern".
    # https://www.iana.org/time-zones
    # https://en.wikipedia.org/wiki/Tz_database
    return pytz.timezone("America/New_York")


# Function returning the current (true, replayed, simulated) wall-clock time as a
# timestamp.
# TODO(gp): maybe GetWallClockTimeFunc is better to clarify that this is a function
#  and not time. We often pass
GetWallClockTime = Callable[[], pd.Timestamp]


# TODO(gp): -> get_wall_clock_time
# TODO(gp): tz -> tz_mode since we are not passing neither a timezone or a
#  timezone_as_str.
def get_current_time(
    tz: str, event_loop: Optional[asyncio.AbstractEventLoop] = None
) -> pd.Timestamp:
    """
    Return current time in UTC / ET timezone or as a naive time.

    This should be the only way to get the current wall-clock time,
    since it handles both wall-clock time and "simulated" wall-clock
    time through asyncio.

    :param tz: how to represent the returned time (e.g., "UTC", "ET", "naive")
    """
    if event_loop is not None:
        # We accept only `hasyncio.EventLoop` here. If we are using standard asyncio
        # EventLoop we rely on wall-clock time instead of `loop.time()`.
        hdbg.dassert_isinstance(event_loop, asyncio.AbstractEventLoop)
        timestamp = event_loop.get_current_time()
    else:
        # Use true real-time.
        timestamp = datetime.datetime.utcnow()
    # Convert it into the right
    timestamp = pd.Timestamp(timestamp, tz=get_UTC_tz())
    if tz == "UTC":
        pass
    elif tz == "ET":
        timestamp = timestamp.tz_convert(get_ET_tz())
    elif tz == "naive_UTC":
        timestamp = timestamp.replace(tzinfo=None)
    elif tz == "naive_ET":
        timestamp = timestamp.tz_convert(get_ET_tz())
        timestamp = timestamp.replace(tzinfo=None)
    else:
        raise ValueError(f"Invalid tz='{tz}'")
    return timestamp


def get_current_timestamp_as_string(tz: str) -> str:
    """
    Return the current time in the format `YYYYMMDD_HHMMSS` (e.g.,
    20210728_221734).

    Note that no information about the timezone is returned. Thus the
    same time corresponds to `20210728_171749` for tz="ET" and
    `20210728_221749` for tz="UTC".
    """
    timestamp = get_current_time(tz)
    ret = timestamp.strftime("%Y%m%d-%H%M%S")
    ret = cast(str, ret)
    return ret


# #############################################################################


def to_generalized_datetime(
    dates: Union[pd.Series, pd.Index], date_standard: Optional[str] = None
) -> Union[pd.Series, pd.Index]:
    """
    Convert string dates to datetime.

    This works like `pd.to_datetime`, but supports more date formats and shifts
    the dates to the end of period instead of the start.

    :param dates: series or index of dates to convert
    :param date_standard: "standard" or "ISO_8601", `None` defaults to
        "standard"
    :return: datetime dates
    """
    # This function doesn't deal with mixed formats.
    hdbg.dassert_isinstance(dates, Iterable)
    hdbg.dassert(not isinstance(dates, str))
    # Try converting to datetime using `pd.to_datetime`.
    format_example_index = -1
    date_example = dates.tolist()[format_example_index]
    format_fix = _handle_incorrect_conversions(date_example)
    if format_fix is not None:
        format_, date_modification_func = format_fix
        dates = dates.map(date_modification_func)
        date_example = dates.tolist()[format_example_index]
    else:
        format_ = None
    datetime_dates = pd.to_datetime(dates, format=format_, errors="coerce")
    # Shift to end of period if conversion has been successful.
    if not pd.isna(datetime_dates).all():
        datetime_example = datetime_dates.tolist()[format_example_index]
        if (
            not pd.isna(datetime_example)
            and datetime_example.strftime("%Y-%m-%d") == date_example
        ):
            return datetime_dates
        shift_func = _shift_to_period_end(date_example)
        if shift_func is not None:
            datetime_dates = datetime_dates.map(shift_func)
        return datetime_dates
    # If standard conversion fails, attempt our own conversion.
    date_standard = date_standard or "standard"
    format_determination_output = _determine_date_format(
        date_example, date_standard
    )
    if format_determination_output is None:
        return datetime_dates
    format_, date_modification_func = format_determination_output
    dates = dates.map(date_modification_func)
    return pd.to_datetime(dates, format=format_)


def _handle_incorrect_conversions(
    date: str,
) -> Optional[Tuple[Optional[str], Callable[[str], str]]]:
    """
    Change data pre-processing for cases when `pd.to_datetime` is mistaken.

    :param date: string date
    :return: date format and a function to apply to string dates before passing
        them into `pd.to_datetime()`
    """
    if len(date) in [7, 8]:
        # "2021-M2" is transformed to '2020-01-01 00:00:01' by
        # `pd.to_datetime`.
        if date[:4].isdigit() and date[4] in ["-", ".", "/"] and date[5] == "M":

            def modify_monthly_date(x: str) -> str:
                year_number = int(x[:4])
                month_number = x[6:]
                num_days_in_month = calendar.monthrange(
                    year_number, int(month_number)
                )[1]
                modified_x = f"{x[:4]}-{month_number}-{num_days_in_month}"
                return modified_x

            return "%Y-%m-%d", modify_monthly_date
    return None


def _shift_to_period_end(  # pylint: disable=too-many-return-statements
    date: str,
) -> Optional[Callable[[StrictDatetime], StrictDatetime]]:
    """
    Get function to shift the dates to the end of period.

    :param date: string date
    :return: a function to shift the dates to the end of period. If `None`, no
        shift is needed
    """

    def shift_to_month_end(x: StrictDatetime) -> StrictDatetime:
        return x + pd.offsets.MonthEnd(0)

    def shift_to_quarter_end(x: StrictDatetime) -> StrictDatetime:
        return x + pd.offsets.QuarterEnd(0)

    def shift_to_year_end(x: StrictDatetime) -> StrictDatetime:
        return x + pd.offsets.YearEnd(0)

    if date[:4].isdigit():
        if len(date) == 7:
            if date[5:].isdigit():
                # "2020-12" format.
                return shift_to_month_end
            if date[5] == "Q":
                # "2021-Q1" format.
                return shift_to_quarter_end
        elif len(date) == 6:
            # "2021Q1" format.
            if date[4] == "Q":
                return shift_to_quarter_end
        elif len(date) == 4:
            # "2021" format.
            return shift_to_year_end
    # "September 2020" of "Sep 2020" format.
    # Get a flat list of month aliases. The full month name comes first.
    month_aliases = sum(dparse.parserinfo().MONTHS, ())[::-1]
    pattern = re.compile("|".join(month_aliases), re.IGNORECASE)
    match = pattern.search(date)
    if match is None:
        return None
    span = match.span()
    date_without_month = f"{date[:span[0]]}{date[span[1]:]}".strip()
    if len(date_without_month) == 4 and date_without_month.isdigit():
        return shift_to_month_end
    return None


def _determine_date_format(
    date: str, date_standard: Optional[str] = None
) -> Optional[Tuple[str, Callable[[str], str]]]:
    """
    Determine date format for cases when `pd.to_datetime` fails.

    :param date: date string
    :param date_standard: "standard" or "ISO_8601", `None` defaults to
        "standard"
    :return: date format and a function to transform date strings before
        converting them to datetime using `pd.to_datetime`
    """
    date_standard = date_standard or "standard"
    if date_standard == "standard":
        year_format = "%Y"
        week_format = "%W"
        day_of_week_format = "%w"
    elif date_standard == "ISO_8601":
        year_format = "%G"
        week_format = "%V"
        day_of_week_format = "%u"
    else:
        raise ValueError(f"Invalid `date_standard`='{date_standard}'")
    # Determine format and original `date` modification function.
    format_ = ""
    if date[:4].isdigit():
        format_ += year_format
    elif date[0] == "Q" and len(date) == 7 and date[-4:].isdigit():
        # "Q1 2020" format.

        def modify_quarterly_data(x: str) -> str:
            year_number = x[-4:]
            quarter = int(x[1:2])
            last_month_of_quarter = 3 * quarter
            last_day_of_quarter = calendar.monthrange(
                int(year_number), last_month_of_quarter
            )[1]
            modified_x = (
                f"{year_number}-{last_month_of_quarter}-{last_day_of_quarter}"
            )
            return modified_x

        format_ = f"{year_format}-%m-%d"
        return format_, modify_quarterly_data
    else:
        _LOG.error("This format is not supported: '%s'", date)
        return None
    next_char = date[4]
    if next_char in ["-", ".", "/", " "]:
        if len(date) not in [7, 8]:
            _LOG.error("This format is not supported: '%s'", date)
            return None
        format_ += "-"
        next_char = date[5]
        if next_char == "W":
            # "2020-W14" format.

            def modify_weekly_date(x: str) -> str:
                x = re.sub(r"[//.\s]", "-", x)
                return x + "-6"

            date_modification_func = modify_weekly_date
            format_ += f"W{week_format}-{day_of_week_format}"
        elif next_char == "S":
            # "2020-S1" - semi-annual format.
            def modify_semiannual_date(x: str) -> str:
                x = re.sub(r"[//.\s]", "-", x)
                return x.replace("S1", "06-30").replace("S2", "12-31")

            date_modification_func = modify_semiannual_date
            format_ += "%m-%d"
        elif next_char == "B":
            # "2020-B1" - bi-monthly format (every other month).
            # We'll index by the start of the month starting with January
            # based on PiT.

            def modify_bimonthly_date(x: str) -> str:
                x = re.sub(r"[//.\s]", "-", x)
                bimonth_number = x[6]
                month_number = int(bimonth_number) * 2 - 1
                modified_x = f"{x[:5]}{month_number}-01"
                return modified_x

            date_modification_func = modify_bimonthly_date
            format_ += "%m-%d"
        else:
            _LOG.error("This format is not supported: '%s'", date)
            return None
    elif next_char == "M" and len(date) == 7:
        # "1959M01" format.

        def modify_monthly_date(x: str) -> str:
            year_number = int(x[:4])
            month_number = x[5:]
            num_days_in_month = calendar.monthrange(
                year_number, int(month_number)
            )[1]
            modified_x = f"{x[:4]}-{month_number}-{num_days_in_month}"
            return modified_x

        date_modification_func = modify_monthly_date
        format_ += "-%m-%d"
    else:
        _LOG.error("This format is not supported: '%s'", date)
        return None
    return format_, date_modification_func


# #############################################################################


def convert_unix_epoch_to_timestamp(
    epoch: int, unit: str = "ms", tz: str = "UTC"
) -> pd.Timestamp:
    """
    Convert Unix epoch to timestamp.

    :param epoch: Unix time epoch
    :param unit: epoch's time unit
    :param tz: resulting timestamp timezone
    :return: timestamp
    """
    timestamp = pd.Timestamp(epoch, unit=unit, tz=tz)
    return timestamp


def convert_timestamp_to_unix_epoch(
    timestamp: pd.Timestamp, unit: str = "ms"
) -> int:
    """
    Convert timestamp to Unix epoch.

    :param timestamp: timestamp
    :param unit: epoch's time unit
    :return: Unix time epoch
    """
    # Make timestamp tz-naive if it is not. Converted to UTC tz before becoming
    # naive automatically.
    if timestamp.tz:
        timestamp = timestamp.tz_convert(None)
    # Convert to epoch.
    epoch: int = (timestamp - pd.Timestamp("1970-01-01")) // pd.Timedelta(
        "1" + unit
    )
    return epoch
