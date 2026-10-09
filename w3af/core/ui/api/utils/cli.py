"""
cli.py

Copyright 2015 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import argparse
from argparse import ArgumentTypeError
from collections.abc import Sequence
from typing import Any

import yaml
from flask import Flask

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
SHA512_HEX_LENGTH = 128
MAX_PORT = 65535
INVALID_PORT = "Invalid port number (1-65535)"
INVALID_CREDENTIAL_HASH = (
    "Error: Please specify a valid"
    " SHA512-hashed plaintext as password,"
    ' either inside a config file with "-c" or'
    ' using the "-p" flag.'
)
CONFIG_SCALAR_TYPES = (str, int, bool)

DEFAULTS: dict[str, Any] = {
    "USERNAME": "admin",
    "HOST": "127.0.0.1",
    "PORT": 5000,
    "DISABLE_SSL": False,
}


def parse_host_port(host: str, port: int | str) -> tuple[str, int]:
    try:
        port_number = int(port)
    except ValueError as value_error:
        raise ArgumentTypeError(INVALID_PORT) from value_error

    if port_number > MAX_PORT or port_number < 0:
        raise ArgumentTypeError(INVALID_PORT)

    if not host:
        raise ArgumentTypeError("Empty bind IP address")

    return host, port_number


def build_parser(description: str = "REST API for w3af") -> argparse.ArgumentParser:
    """
    :return: The parser with the server options shared by the w3af web services
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "host:port",
        action="store",
        help="Specify address where the service will listen for HTTP requests."
        " If not specified 127.0.0.1:5000 will be used.",
        default=False,
        nargs="?",
    )

    parser.add_argument(
        "--no-ssl", dest="disable_ssl", action="store_true", help="Disable SSL support"
    )

    parser.add_argument(
        "-c",
        default=False,
        dest="config_file",
        help="Path to a config file in YAML format. At minimum,"
        ' either this OR the "-p" (password) option MUST'
        " be provided.",
    )

    opts = parser.add_argument_group(
        "server options",
        "Server options can be specified here or"
        " as part of a YAML configuration file"
        ' using the "-c" command line argument.',
    )

    opts.add_argument(
        "-p",
        required=False,
        default=False,
        dest="password",
        help="SHA512-hashed password for HTTP basic"
        " authentication. Linux or Mac users can generate"
        " the hash running:\n"
        ' echo -n "password" | sha512sum',
    )

    opts.add_argument(
        "-u",
        required=False,
        dest="username",
        default=False,
        help="Username required for basic auth. If not "
        'specified, this will be set to "admin".',
    )

    opts.add_argument(
        "-v",
        required=False,
        default=False,
        dest="verbose",
        action="store_true",
        help="Enables verbose output",
    )

    return parser


def parse_arguments(
    argv: Sequence[str] | None = None,
    parser: argparse.ArgumentParser | None = None,
) -> argparse.Namespace:
    """
    Parses the command line arguments
    :return: The parse result from argparse
    """
    parser = parser or build_parser()
    args = parser.parse_args(argv)

    host_port = getattr(args, "host:port")
    if host_port:
        try:
            args.host, args.port = host_port.split(":")
        except ValueError as value_error:
            raise ArgumentTypeError(
                "Please specify a valid host and port"
                ' as HOST:PORT (eg "127.0.0.1:5000").'
            ) from value_error

    return args


def load_config_file(app: Flask, args: argparse.Namespace, config_file: str) -> None:
    """
    Copy the scalar settings of the YAML configuration file to the app config
    """
    try:
        with open(config_file, encoding="utf-8") as handle:
            yaml_conf = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as load_error:
        raise ArgumentTypeError(
            f"Error loading config file {config_file}. Please check"
            " it exists and is a valid YAML file."
        ) from load_error

    if not isinstance(yaml_conf, dict):
        raise ArgumentTypeError(
            f"Error loading config file {config_file}. The YAML document"
            " must be a mapping of option names to values."
        )

    for key, value in yaml_conf.items():
        if not isinstance(value, CONFIG_SCALAR_TYPES):
            continue

        if vars(args).get(key.lower()):
            raise ArgumentTypeError(
                "Error: you appear to have specified"
                " options in the config file and on the"
                " command line. Please resolve any"
                f" conflicting options and try again: {key}"
            )

        app.config[key.upper()] = value


def validate_password(password: str) -> None:
    """
    Check that the password is a 512-bit hex string (ie, a SHA512 hash)
    """
    try:
        int(password, 16)
    except (TypeError, ValueError) as error:
        raise ArgumentTypeError(INVALID_CREDENTIAL_HASH) from error

    if len(password) != SHA512_HEX_LENGTH:
        raise ArgumentTypeError(INVALID_CREDENTIAL_HASH)


def warn_about_public_bind(app: Flask) -> None:
    print()
    if "PASSWORD" not in app.config:
        print(
            "WARNING! Running this service on a public IP might expose your"
            " system to vulnerabilities such as arbitrary file reads"
            " through file:// protocol specifications in target URLs and"
            " scan profiles.\n\n"
            "We recommend enabling HTTP basic authentication by"
            " specifying a password on the command line (with"
            ' "-p <SHA512 hash>") or in a configuration file.\n'
        )

    if app.config["DISABLE_SSL"]:
        print(
            "WARNING! Traffic to this service is not encrypted and could be"
            " sniffed. Please consider using an SSL-enabled proxy such as"
            " nginx, or removing --no-ssl from the command line.\n"
        )
    else:
        print(
            "WARNING! Traffic to this service is encrypted using self-signed"
            " certificates.\n"
        )


def process_cmd_args_config(
    app: Flask,
    argv: Sequence[str] | None = None,
    parser: argparse.ArgumentParser | None = None,
) -> argparse.Namespace:
    """
    Handle/merge the command line arguments and configuration file
    :return: The result of argparse'ing the command line, the app is configured
    """
    args = parse_arguments(argv, parser)

    if args.config_file:
        load_config_file(app, args, args.config_file)

    for name, value in vars(args).items():
        if isinstance(value, CONFIG_SCALAR_TYPES) and value:
            app.config[name.upper()] = value

    for key, value in DEFAULTS.items():
        app.config.setdefault(key, value)

    if "PASSWORD" in app.config:
        validate_password(app.config["PASSWORD"])

    app.config["HOST"], app.config["PORT"] = parse_host_port(
        app.config["HOST"], app.config["PORT"]
    )

    if app.config["HOST"] not in LOOPBACK_HOSTS:
        warn_about_public_bind(app)

    return args
