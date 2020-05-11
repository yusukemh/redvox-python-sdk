"""
This module provides a command line interface (CLI) for converting, viewing, and downloading RedVox data files.
"""

import argparse
import logging
import os.path
import sys
from typing import Dict, List, Optional

import redvox.cli.conversions as conversions
import redvox.cli.data_req as data_req

# pylint: disable=C0103
log = logging.getLogger(__name__)


def check_path(path: str, path_is_file: bool = True, file_ext: Optional[str] = None) -> bool:
    """
    Checks that the passed in path exists.
    :param path: The path to check.
    :param path_is_file: The path is a file when True or a directory when False.
    :return: True if the path exists, False otherwise.
    """
    if path_is_file:
        return os.path.isfile(path) and (file_ext is None or os.path.basename(path).endswith(file_ext))
    else:
        return os.path.isdir(path)


def check_files(paths: List[str], file_ext: Optional[str] = None) -> bool:
    """
    Checks this given files to determine if they exist.
    :param paths: The paths to check.
    :param file_ext: An optional file extension to filter against.
    :return: True if all paths exist, False otherwise
    """
    invalid_paths: List[str] = list(filter(lambda path: not check_path(path, file_ext=file_ext), paths))
    if len(invalid_paths) > 0:
        log.error("%d invalid paths found", len(invalid_paths))
        for invalid_path in invalid_paths:
            log.error("Invalid path %s", invalid_path)
        return False
    return True


def check_out_dir(out_dir: Optional[str] = None) -> bool:
    """
    Checks if a given directory exists.
    :param out_dir: The directory to check.
    :return: True if it exists, False otherwise.
    """
    if out_dir is not None and not check_path(out_dir, path_is_file=False):
        log.error("out_dir is invalid: %s", out_dir)
        return False
    return True


def determine_exit(status: bool) -> None:
    """
    Determine the exit status and exit the CLI.
    :param status: True will exit with a status of 0 and False will exit with a status of 1.
    """
    if status:
        log.info("Exiting with status = 0")
        sys.exit(0)

    log.error("Exiting with status = 1")
    sys.exit(1)


def rdvxz_to_rdvxm(args) -> None:
    if not check_files(args.rdvxz_paths, ".rdvxz"):
        determine_exit(False)

    if not check_out_dir(args.out_dir):
        determine_exit(False)

    determine_exit(conversions.rdvxz_to_rdvxm(args.rdvxz_paths, args.out_dir))


def rdvxm_to_rdvxz(args) -> None:
    if not check_files(args.rdvxm_paths, ".rdvxm"):
        determine_exit(False)

    if not check_out_dir(args.out_dir):
        determine_exit(False)

    determine_exit(conversions.rdvxm_to_rdvxz(args.rdvxm_paths, args.out_dir))


def rdvxz_to_json_args(args) -> None:
    """
    Wrapper function that calls the to_json conversion.
    :param args: Args from argparse.
    """
    if not check_files(args.rdvxz_paths, ".rdvxz"):
        determine_exit(False)

    if not check_out_dir(args.out_dir):
        determine_exit(False)

    determine_exit(conversions.rdvxz_to_json(args.rdvxz_paths, args.out_dir))


def rdvxm_to_json_args(args) -> None:
    """
    Wrapper function that calls the to_json conversion.
    :param args: Args from argparse.
    """
    if not check_files(args.rdvxm_paths, ".rdvxm"):
        determine_exit(False)

    if not check_out_dir(args.out_dir):
        determine_exit(False)

    determine_exit(conversions.rdvxm_to_json(args.rdvxm_paths, args.out_dir))


def json_to_rdvxz_args(args) -> None:
    """
    Wrapper function that calls the to_rdvxz conversion.
    :param args: Args from argparse.
    """
    if not check_files(args.json_paths, ".json"):
        determine_exit(False)

    if not check_out_dir(args.out_dir):
        determine_exit(False)

    determine_exit(conversions.json_to_rdvxz(args.json_paths, args.out_dir))


def json_to_rdvxm_args(args) -> None:
    """
    Wrapper function that calls the to_rdvxm conversion.
    :param args: Args from argparse.
    """
    if not check_files(args.json_paths, ".json"):
        determine_exit(False)

    if not check_out_dir(args.out_dir):
        determine_exit(False)

    determine_exit(conversions.json_to_rdvxm(args.json_paths, args.out_dir))


def rdvxz_print_stdout_args(args) -> None:
    """
    Wrapper function that calls the print to stdout.
    :param args: Args from argparse.
    """
    if not check_files(args.rdvxz_paths, ".rdvxz"):
        determine_exit(False)

    determine_exit(conversions.rdvxz_print_stdout(args.rdvxz_paths))


def rdvxm_print_stdout_args(args) -> None:
    """
    Wrapper function that calls the print to stdout.
    :param args: Args from argparse.
    """
    if not check_files(args.rdvxm_paths, ".rdvxm"):
        determine_exit(False)

    determine_exit(conversions.rdvxm_print_stdout(args.rdvxm_paths))


def validate_rdvxm_args(args) -> None:
    if not check_files(args.rdvxm_paths, ".rdvxm"):
        determine_exit(False)

    determine_exit(conversions.validate_rdvxm(args.rdvxm_paths))


def data_req_args(args) -> None:
    """
    Wrapper function that calls the data_req.
    :param args: Args from argparse.
    """
    if not check_out_dir(args.out_dir):
        determine_exit(False)

    determine_exit(data_req.make_data_req(args.out_dir,
                                          args.protocol,
                                          args.host,
                                          args.port,
                                          args.email,
                                          args.password,
                                          args.req_start_s,
                                          args.req_end_s,
                                          args.redvox_ids,
                                          args.retries,
                                          args.auth_token))


def main():
    """
    Entry point into the CLI.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser("redvox-cli",
                                                              description="Command line tools for viewing, converting,"
                                                                          " and downloading RedVox data.")
    parser.add_argument("--verbose",
                        "-v",
                        help="Enable verbose logging",
                        action="count",
                        default=0)

    sub_parser = parser.add_subparsers()
    sub_parser.required = True
    sub_parser.dest = "command"

    # rdvxz -> rdvxm
    rdvxz_to_rdvxm_parser = sub_parser.add_parser("rdvxz_to_rdvxm",
                                                  help="Convert rdvxz (API 900) to rdvxm (API 1000/M) files")
    rdvxz_to_rdvxm_parser.add_argument("rdvxz_paths",
                                       help="One or more rdvxz files to convert to json files",
                                       nargs="+")
    rdvxz_to_rdvxm_parser.add_argument("--out_dir",
                                       "-o",
                                       help="Optional output directory (will use same directory as source files by "
                                            "default)")
    rdvxz_to_rdvxm_parser.set_defaults(func=rdvxz_to_rdvxm)

    # rdvxm -> rdvxz
    rdvxm_to_rdvxz_parser = sub_parser.add_parser("rdvxm_to_rdvxz",
                                                  help="Convert rdvxm (API 1000/M) to rdvxx (API 900) files")
    rdvxm_to_rdvxz_parser.add_argument("rdvxm_paths",
                                       help="One or more rdvxm files to convert to json files",
                                       nargs="+")
    rdvxm_to_rdvxz_parser.add_argument("--out_dir",
                                       "-o",
                                       help="Optional output directory (will use same directory as source files by "
                                            "default)")
    rdvxm_to_rdvxz_parser.set_defaults(func=rdvxm_to_rdvxz)

    # rdvxz -> json
    rdvxz_to_json_parser = sub_parser.add_parser("rdvxz_to_json",
                                                 help="Convert rdvxz files to json files")
    rdvxz_to_json_parser.add_argument("rdvxz_paths",
                                      help="One or more rdvxz files to convert to json files",
                                      nargs="+")
    rdvxz_to_json_parser.add_argument("--out_dir",
                                      "-o",
                                      help="Optional output directory (will use same directory as source files by "
                                           "default)")
    rdvxz_to_json_parser.set_defaults(func=rdvxz_to_json_args)

    rdvxm_to_json_parser = sub_parser.add_parser("rdvxm_to_json",
                                                 help="Convert rdvxm files to json files")
    rdvxm_to_json_parser.add_argument("rdvxm_paths",
                                      help="One or more rdvxm files to convert to json files",
                                      nargs="+")
    rdvxm_to_json_parser.add_argument("--out_dir",
                                      "-o",
                                      help="Optional output directory (will use same directory as source files by "
                                           "default)")
    rdvxm_to_json_parser.set_defaults(func=rdvxm_to_json_args)

    # json -> rdvxz
    json_to_rdvxz_parser = sub_parser.add_parser("json_to_rdvxz",
                                                 help="Convert json files to rdvxz files")
    json_to_rdvxz_parser.add_argument("json_paths",
                                      help="One or more json files to convert to rdvxz files",
                                      nargs="+")
    json_to_rdvxz_parser.add_argument("--out_dir",
                                      "-o",
                                      help="Optional output directory (will use same directory as source files by "
                                           "default)")
    json_to_rdvxz_parser.set_defaults(func=json_to_rdvxz_args)

    json_to_rdvxm_parser = sub_parser.add_parser("json_to_rdvxm",
                                                 help="Convert json files to rdvxm files")
    json_to_rdvxm_parser.add_argument("json_paths",
                                      help="One or more json files to convert to rdvxm files",
                                      nargs="+")
    json_to_rdvxm_parser.add_argument("--out_dir",
                                      "-o",
                                      help="Optional output directory (will use same directory as source files by "
                                           "default)")
    json_to_rdvxm_parser.set_defaults(func=json_to_rdvxm_args)

    # print
    rdvxz_print_parser = sub_parser.add_parser("printz",
                                               help="Print contents of rdvxz files to stdout")
    rdvxz_print_parser.add_argument("rdvxz_paths",
                                    help="One or more rdvxz files to print",
                                    nargs="+")
    rdvxz_print_parser.set_defaults(func=rdvxz_print_stdout_args)

    rdvxm_print_parser = sub_parser.add_parser("printm",
                                               help="Print contents of rdvxm files to stdout")
    rdvxm_print_parser.add_argument("rdvxm_paths",
                                    help="One or more rdvxm files to print",
                                    nargs="+")
    rdvxm_print_parser.set_defaults(func=rdvxm_print_stdout_args)

    # validation
    rdvxm_validation_parser = sub_parser.add_parser("validatem",
                                                    help="Validate the structure of API M files")
    rdvxm_validation_parser.add_argument("rdvxm_paths",
                                         help="One or more rdvxm files to print",
                                         nargs="+")
    rdvxm_validation_parser.set_defaults(func=validate_rdvxm_args)

    # data_req
    data_req_parser = sub_parser.add_parser("data_req",
                                            help="Request bulk RedVox data from the RedVox servers")
    data_req_parser.add_argument("--out_dir",
                                 "-o",
                                 help="The output directory that RedVox files will be written to (default=.)",
                                 default=".")
    data_req_parser.add_argument("--retries",
                                 "-r",
                                 help="The number of times the client should retry getting a file on failure "
                                      "(default=1)",
                                 default=1,
                                 choices=set(range(0, 6)),
                                 type=int)
    data_req_parser.add_argument("--host",
                                 "-H",
                                 help="Data server host (default=redvox.io)",
                                 default="redvox.io")
    data_req_parser.add_argument("--port",
                                 "-p",
                                 type=int,
                                 help="Data server port (default=443)",
                                 default=443)
    data_req_parser.add_argument("--protocol",
                                 help="One of either http or https (default https)",
                                 choices=["https", "http"],
                                 default="https")
    data_req_parser.add_argument("auth_token",
                                 help="An authentication token provided by RedVox required for accessing the data "
                                      "request service")
    data_req_parser.add_argument("email",
                                 help="redvox.io account email")
    data_req_parser.add_argument("password",
                                 help="redvox.io account password")
    data_req_parser.add_argument("req_start_s",
                                 type=int,
                                 help="Data request start as number of seconds since the epoch UTC")
    data_req_parser.add_argument("req_end_s",
                                 type=int,
                                 help="Data request end as number of seconds since the epoch UTC")
    data_req_parser.add_argument("redvox_ids",
                                 nargs="+",
                                 help="A list of RedVox ids delimited by a space")
    data_req_parser.set_defaults(func=data_req_args)

    # Parse the args
    args = parser.parse_args()

    # Setup logging
    log_levels: Dict[int, str] = {
        0: "WARN",
        1: "INFO",
        2: "DEBUG"
    }
    log_level: str = log_levels[args.verbose] if args.verbose in log_levels else log_levels[0]
    logging.basicConfig(level=log_level,
                        format="[%(levelname)s:%(process)d:%(filename)s:%(module)s:%(funcName)s:%(lineno)d:%(asctime)s]"
                               " %(message)s")

    log.info("Running with args=%s and log_level=%s",
             str(args),
             log_level)

    # Try calling the appropriate handler
    # pylint: disable=W0703
    try:
        args.func(args)
    except Exception as e:
        log.error("Encountered an error: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
