"""Command-line interface for Agentman."""

import argparse
import errno
import shutil
import sys
import tempfile
from pathlib import Path

from agentman.agent_builder import build_from_agentfile
from agentman.agentfile_parser import AgentfileParser
from agentman.common import perror
from agentman.version import print_version


def resolve_context_path(path: str) -> Path:
    """Resolve and validate the build context path."""
    context_path = Path(path).resolve()
    if not context_path.exists():
        raise ValueError(f"Build context path not found: {context_path}")
    if context_path.is_file():
        return context_path.parent
    return context_path


def build_cli(args: argparse.Namespace) -> None:
    """Build agent files from an Agentfile."""
    context_path = resolve_context_path(args.path)
    agentfile_path = context_path / args.file
    if not agentfile_path.exists():
        raise ValueError(f"Agentfile not found: {agentfile_path}")

    output_dir = context_path / (args.output or "agent")
    build_from_agentfile(str(agentfile_path), str(output_dir))


def validate_cli(args: argparse.Namespace) -> None:
    """Validate an Agentfile and, optionally, its generated output."""
    context_path = resolve_context_path(args.path)
    agentfile_path = context_path / args.file
    if not agentfile_path.exists():
        raise ValueError(f"Agentfile not found: {agentfile_path}")

    parser = AgentfileParser()
    config = parser.parse_file(str(agentfile_path))

    if args.build_check:
        temp_dir = Path(tempfile.mkdtemp(prefix="agentman-validate-"))
        try:
            build_from_agentfile(str(agentfile_path), str(temp_dir))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    if args.quiet:
        return

    print(f"✅ Valid Agentfile: {agentfile_path}")
    for orchestrator in config.orchestrators.values():
        print(f"   - orchestrator: {orchestrator.name}")
        if orchestrator.stage_schema:
            print(f"   - stage schema: {orchestrator.stage_schema}")
            print(f"   - stages: {len(orchestrator.stages)}")


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="agentman",
        description="A deterministic Agentfile parser and generator",
    )
    parser.add_argument("--debug", action="store_true", help="display debug messages")
    parser.add_argument("--quiet", "-q", action="store_true", help="reduce output")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    build_parser = subparsers.add_parser("build", help="generate runtime files from an Agentfile")
    build_parser.add_argument("-f", "--file", default="Agentfile", help="name of the Agentfile")
    build_parser.add_argument("-o", "--output", help="output directory for generated files")
    build_parser.add_argument("path", nargs="?", default=".", help="build context directory")
    build_parser.set_defaults(func=build_cli)

    validate_parser = subparsers.add_parser("validate", help="validate an Agentfile and stage schema")
    validate_parser.add_argument("-f", "--file", default="Agentfile", help="name of the Agentfile")
    validate_parser.add_argument(
        "--build-check",
        action="store_true",
        help="also perform a throwaway build to verify generated output",
    )
    validate_parser.add_argument("path", nargs="?", default=".", help="validation context directory")
    validate_parser.set_defaults(func=validate_cli)

    version_parser = subparsers.add_parser("version", help="show the Agentman version information")
    version_parser.set_defaults(func=print_version)

    return parser


def main() -> None:
    """Main entry point for the CLI application."""
    parser = create_parser()
    args = parser.parse_args()

    def eprint(error: Exception, exit_code: int) -> None:
        perror("Error: " + str(error).strip("'\""))
        sys.exit(exit_code)

    try:
        args.func(args)
    except KeyError as error:
        eprint(error, 1)
    except NotImplementedError as error:
        eprint(error, errno.ENOTSUP)
    except KeyboardInterrupt:
        sys.exit(0)
    except (ConnectionError, IndexError, ValueError) as error:
        eprint(error, errno.EINVAL)
    except IOError as error:
        eprint(error, errno.EIO)
