#!/usr/bin/env python
"""
Script to download OHLCV data for a single exchange from Talos.

Use as:

# Download OHLCV data for binance 'v03', saving dev_stage:
> im_v2/talos/data/extract/download_realtime_for_one_exchange.py \
    --start_timestamp '20211110-101100' \
    --end_timestamp '20211110-101200' \
    --exchange_id 'binance' \
    --universe 'v03' \
    --db_stage 'dev' \
    --db_table 'talos_ohlcv' \
    --api_stage 'sandbox' \
    --aws_profile 'ck' \
    --s3_path 's3://cryptokaizen-data/real_time/talos'
"""

import argparse
import logging

import helpers.hdbg as hdbg
import helpers.hparser as hparser
import helpers.hs3 as hs3
import im_v2.common.data.extract.extract_utils as imvcdeexut
import im_v2.common.db.db_utils as imvcddbut
import im_v2.talos.data.extract.exchange_class as imvtdeexcl

_LOG = logging.getLogger(__name__)


def _parse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--api_stage",
        action="store",
        required=False,
        default="sandbox",
        type=str,
        help="(Optional) API 'stage' to use ('sandbox' or 'prod'), default: 'sandbox'",
    )
    parser.add_argument("--incremental", action="store_true")
    parser = hparser.add_verbosity_arg(parser)
    parser = imvcdeexut.add_exchange_download_args(parser)
    parser = imvcddbut.add_db_args(parser)
    parser = hs3.add_s3_args(parser)
    return parser  # type: ignore[no-any-return]


def _main(parser: argparse.ArgumentParser) -> None:
    args = parser.parse_args()
    hdbg.init_logger(verbosity=args.log_level, use_exec_path=True)
    imvcdeexut.download_realtime_for_one_exchange(args, imvtdeexcl.TalosExchange)


if __name__ == "__main__":
    _main(_parse())
