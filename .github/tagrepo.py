#!/usr/bin/env python3
"""Automatically tags repo based on changes that are expected."""
# Standard Library Imports
import argparse
import logging
import logging.config
import os
import pathlib
import re
import sys

# Third Party Imports
import autotag
import docker
from pylib.argparse import CustomHelpFormatter
from pylib.versions import (
    JenkinsVersion,
    VersionUpdateTypes,
)

# Local Application Imports

# constants and other program configurations
_PROGNAME = os.path.basename(os.path.abspath(__file__))
_arg_parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=lambda prog: CustomHelpFormatter(
        prog, max_help_position=35
    ),
    allow_abbrev=False,
)

_DOCKERFILE = "Dockerfile"
_JENKINS_DOCKER_IMAGE = "jenkins/jenkins:lts"
_JENKINS_VERSION_ENV_VAR_NAME = "JENKINS_VERSION"
PRIOR_JENKINS_DOCKER_IMAGE = rf"(?<=-FROM ){_JENKINS_DOCKER_IMAGE}@sha256:\w+"
CURRENT_JENKINS_DOCKER_IMAGE = (
    rf"(?<=\+FROM ){_JENKINS_DOCKER_IMAGE}@sha256:\w+"
)

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
            },
        },
        "loggers": {
            "": {"level": "INFO", "handlers": ["console"]},
        },
    }
)

_logger = logging.getLogger(__name__)


def retrieve_cmd_args():
    """Retrieve command arguments from the command line.

    Returns
    -------
    Namespace
        An object that holds attributes pulled from the command line.

    Raises
    ------
    SystemExit
        If user input is not considered valid when parsing arguments.

    """
    autotag_arg_parser = autotag.modify_arg_parser(_arg_parser)

    args = vars(autotag_arg_parser.parse_args())
    return args


def update_policy(patch, repo_working_dir):
    """Determine the update types in this repository from the previous commits.

    Parameters
    ----------
    patch : git.diff.DiffIndex
        The index of changes between two git commits.
    repo_working_dir : str
        The git working directory path.

    Returns
    -------
    repo_update_types : list of pylib.versions.VersionUpdateTypes
        The update types found from the changes.

    """
    repo_update_types = list()
    for chd_object in patch:
        chd_file_path = pathlib.PurePath(repo_working_dir).joinpath(
            chd_object.b_path
        )
        patch_text = chd_object.diff.decode("utf-8")

        if chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            _DOCKERFILE
        ) and re.findall(PRIOR_JENKINS_DOCKER_IMAGE, patch_text):
            _logger.info(f"detected base image digest change in {_DOCKERFILE}")
            prior_jenkins_img = re.findall(
                PRIOR_JENKINS_DOCKER_IMAGE, patch_text
            )[0]
            current_jenkins_img = re.findall(
                CURRENT_JENKINS_DOCKER_IMAGE, patch_text
            )[0]
            _logger.info(f"prior Jenkins Docker image: {prior_jenkins_img}")
            _logger.info(
                f"current Jenkins Docker image: {current_jenkins_img}"
            )

            docker_client = docker.from_env()
            prior_jenkins_version = JenkinsVersion.from_docker_image(
                docker_client, prior_jenkins_img
            )
            current_jenkins_version = JenkinsVersion.from_docker_image(
                docker_client, current_jenkins_img
            )
            _logger.info(f"prior Jenkins version: {prior_jenkins_version}")
            _logger.info(f"current Jenkins version: {current_jenkins_version}")

            types_of_jenkins_update = (
                prior_jenkins_version.determine_update_types(
                    current_jenkins_version
                )
            )
            _logger.info(
                "detected jenkins version updates between "
                f"Jenkins versions: {types_of_jenkins_update}"
            )

            # In the event that the Jenkins maintainers decided to increment
            # multiple parts of the jenkins versioning. I only want to denote
            # the greatest part that has changed.
            greatest_jenkins_update_type = (
                JenkinsVersion.determine_greatest_update_type(
                    types_of_jenkins_update
                )
            )

            if greatest_jenkins_update_type == VersionUpdateTypes.PATCH:
                repo_update_types.append(VersionUpdateTypes.PATCH)
            elif greatest_jenkins_update_type == VersionUpdateTypes.MINOR:
                repo_update_types.append(VersionUpdateTypes.MINOR)
            elif greatest_jenkins_update_type == VersionUpdateTypes.MAJOR:
                raise SystemExit(
                    "\n\n"
                    + "WARNING: The current Jenkins image has had a major jenkins version update.\n"  # noqa: E501,W503
                    + f"({prior_jenkins_version} -> {current_jenkins_version})\n"  # noqa: E501,W503
                    + "Manual tagging will need to occur for this kind of update.\n"  # noqa: E501,W503
                )
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            _DOCKERFILE
        ):
            _logger.info(f"detected general {_DOCKERFILE} changes")
            repo_update_types.append(VersionUpdateTypes.MINOR)
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            "casc.yaml"
        ):
            _logger.info("detected casc file changes")
            repo_update_types.append(VersionUpdateTypes.MINOR)
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            "plugins.txt"
        ):
            repo_update_types.append(VersionUpdateTypes.RESEAT)

    return repo_update_types


def main(args):
    """Start the main program execution."""
    _logger.info(f"started {_PROGNAME}")
    autotag.run(args, update_policy)


if __name__ == "__main__":
    args = retrieve_cmd_args()
    main(args)
    sys.exit(0)
