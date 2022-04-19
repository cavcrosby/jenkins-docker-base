#!/usr/bin/env python3
"""Automatically tags repo based on changes that are expected."""
# Standard Library Imports
import argparse
import enum
import logging
import os
import pathlib
import re
import sys

# Third Party Imports
import docker
import git

# Local Application Imports
import pylib

# constants and other program configurations
_PROGNAME = os.path.basename(os.path.abspath(__file__))
_arg_parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=lambda prog: pylib.argparse.CustomHelpFormatter(
        prog, max_help_position=35
    ),
    allow_abbrev=False,
)

# TODO(cavcrosby): ENV_VAR_REGEX was copied over from another project. See
# about integrating this into pylib?
ENV_VAR_REGEX = r"^[a-zA-Z_]\w*=.+"
_DOCKERFILE = "Dockerfile"
_JENKINS_DOCKER_IMAGE = "jenkins/jenkins:lts"
_JENKINS_VERSION_ENV_VAR_NAME = "JENKINS_VERSION"
PRIOR_JENKINS_DOCKER_IMAGE = rf"(?<=-FROM ){_JENKINS_DOCKER_IMAGE}@sha256:\w+"
CURRENT_JENKINS_DOCKER_IMAGE = (
    rf"(?<=\+FROM ){_JENKINS_DOCKER_IMAGE}@sha256:\w+"
)

# positional and option arg labels
# used at the command line and to reference values of arguments

PUSH_SHORT_OPTION = "p"
PUSH_LONG_OPTION = "push"

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

_console_handler.setFormatter(_formatter)
_logger.addHandler(_console_handler)


class SemanticVersion:
    """Represent a semantic version.

    Parameters
    ----------
    version : str
        A semantic version string (e.g. 1.2.3, 3.2.2).

    Attributes
    ----------
    SEMANTIC_VERSION_REGEX : str
        The regex used to extract the different parts of the semantic
        versioning.

    """

    _MAJOR_CAPTURE_GROUP = 1
    _MINOR_CAPTURE_GROUP = 2
    _PATCH_CAPTURE_GROUP = 3

    # for reference on where I got this regex from:
    # https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
    SEMANTIC_VERSION_REGEX = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"  # noqa: E501

    def __init__(self, version):
        """Construct the semantic version object."""
        semantic_groups = re.match(self.SEMANTIC_VERSION_REGEX, version)
        self.major = int(semantic_groups[self._MAJOR_CAPTURE_GROUP])
        self.minor = int(semantic_groups[self._MINOR_CAPTURE_GROUP])
        self.patch = int(semantic_groups[self._PATCH_CAPTURE_GROUP])

    @classmethod
    def determine_update_types(cls, v1, v2):
        """Determine the update types between two semantic versions.

        Parameters
        ----------
        v1 : autotag.SemanticVersion
            A semantic version object.
        v2 : autotag.SemanticVersion
            A semantic version object.

        Notes
        -----
        When going from one semantic version to another. It's normal to
        consider whether the new version is considered a patch, minor, or major
        update to the previous version.

        """
        update_types = list()
        if abs(v1.major - v2.major) > 0:
            update_types.append(SemanticVersionUpdateTypes.MAJOR)
        if abs(v1.minor - v2.minor) > 0:
            update_types.append(SemanticVersionUpdateTypes.MINOR)
        if abs(v1.patch - v2.patch) > 0:
            update_types.append(SemanticVersionUpdateTypes.PATCH)

        return update_types

    def increment_major(self, by):
        """Increment the semantic versioning major by a given amount.

        Parameters
        ----------
        by : int
            The amount to increment the semantic versioning major by.

        """
        self.major += by

    def increment_minor(self, by):
        """Increment the semantic versioning minor by a given amount.

        Parameters
        ----------
        by : int
            The amount to increment the semantic versioning minor by.

        """
        self.minor += by

    def increment_patch(self, by):
        """Increment the semantic versioning patch by a given amount.

        Parameters
        ----------
        by : int
            The amount to increment the semantic versioning patch by.

        """
        self.patch += by

    def __eq__(self, v):
        """Determine if the semantic version is equal to this instance."""
        return (
            f"{self.major}.{self.minor}.{self.patch}"
            == f"{v.major}.{v.minor}.{v.patch}"  # noqa: W503
        )

    def __str__(self):
        """Return the string representation of an instance."""
        return f"{self.major}.{self.minor}.{self.patch}"


class SemanticVersionUpdateTypes(enum.Enum):
    """Represent values that designate type of semantic versioning update."""

    MAJOR = enum.auto()
    MINOR = enum.auto()
    PATCH = enum.auto()


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
    _arg_parser.add_argument(
        f"-{PUSH_SHORT_OPTION}",
        f"--{PUSH_LONG_OPTION}",
        action="store_true",
        help="push the locally created tags to the remote origin",
    )

    args = vars(_arg_parser.parse_args())
    return args


def get_jenkins_version(docker_client, docker_image):
    """Fetch the Jenkins version from a Jenkins Docker image.

    Parameters
    ----------
    docker_client : docker.client.DockerClient
        The Docker client object.
    docker_image : str
        The qualified Docker image name.

    Returns
    -------
    str or None
        The Jenkins version, or None if no version was found.

    """
    # There does not currently appear to be a way to examine a Docker image
    # without pulling the image first. At least through Docker's Python SDK.
    jenkins_env_vars = docker_client.images.pull(docker_image).attrs["Config"][
        "Env"
    ]
    docker_client.images.remove(docker_image)

    for env_var in jenkins_env_vars:
        regex = re.compile(ENV_VAR_REGEX)
        if regex.search(env_var) and (
            _JENKINS_VERSION_ENV_VAR_NAME  # noqa: W503
            == env_var.split("=")[0]  # noqa: W503
        ):
            return env_var.split("=")[1]

    return None


def main(args):
    """Start the main program execution."""
    _logger.info(f"started {_PROGNAME}")
    this_repo = git.Repo(os.getcwd(), search_parent_directories=True)
    repo_working_dir = this_repo.working_tree_dir
    latest_version = SemanticVersion(
        str(
            sorted(this_repo.tags, key=lambda tagref: str(tagref))[-1]
        ).replace("v", "")
    )
    new_latest_version = SemanticVersion(str(latest_version))

    # the 'R' kwargs parameter swaps both sides of a diff
    patch = this_repo.head.commit.diff("HEAD~1", create_patch=True, R=True)

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
            prior_jenkins_version = SemanticVersion(
                get_jenkins_version(docker_client, prior_jenkins_img)
            )
            current_jenkins_version = SemanticVersion(
                get_jenkins_version(docker_client, current_jenkins_img)
            )
            _logger.info(f"prior Jenkins version: {prior_jenkins_version}")
            _logger.info(f"current Jenkins version: {current_jenkins_version}")

            types_of_jenkins_update = SemanticVersion.determine_update_types(
                prior_jenkins_version, current_jenkins_version
            )
            _logger.info(
                "detected semantic version updates between "
                f"Jenkins versions: {types_of_jenkins_update}"
            )

            greatest_update_type = None
            # In the event that the Jenkins maintainers decided to increment
            # multiple parts of the semantic versioning. I only want to denote
            # the greatest part that has changed.
            #
            # major > minor > patch
            for type_of_jenkins_update in types_of_jenkins_update:
                if (
                    type_of_jenkins_update == SemanticVersionUpdateTypes.PATCH
                    and (  # noqa: W503
                        greatest_update_type
                        != SemanticVersionUpdateTypes.MINOR  # noqa: W503
                        and greatest_update_type  # noqa: W503
                        != SemanticVersionUpdateTypes.MAJOR  # noqa: W503
                    )
                ):
                    greatest_update_type = SemanticVersionUpdateTypes.PATCH
                elif (
                    type_of_jenkins_update == SemanticVersionUpdateTypes.MINOR
                    and (  # noqa: W503
                        greatest_update_type
                        != SemanticVersionUpdateTypes.MAJOR  # noqa: W503
                    )
                ):
                    greatest_update_type = SemanticVersionUpdateTypes.MINOR
                elif (
                    type_of_jenkins_update == SemanticVersionUpdateTypes.MAJOR
                ):
                    greatest_update_type = SemanticVersionUpdateTypes.MAJOR

            if greatest_update_type == SemanticVersionUpdateTypes.PATCH:
                new_latest_version.increment_patch(1)
            elif greatest_update_type == SemanticVersionUpdateTypes.MINOR:
                new_latest_version.increment_minor(1)
            elif greatest_update_type == SemanticVersionUpdateTypes.MAJOR:
                raise SystemExit(
                    "\n\n"
                    + "WARNING: The current Jenkins image has had a major semantic version update.\n"  # noqa: E501,W503
                    + f"({prior_jenkins_version} -> {current_jenkins_version})\n"  # noqa: E501,W503
                    + "Manual tagging will need to occur for this kind of update.\n"  # noqa: E501,W503
                )
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            _DOCKERFILE
        ):
            _logger.info(f"detected general {_DOCKERFILE} changes")
            new_latest_version.increment_minor(1)
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            "casc.yaml"
        ):
            _logger.info("detected casc file changes")
            new_latest_version.increment_minor(1)

    _logger.info(f"the prior latest repo version: {latest_version}")
    _logger.info(f"the final new latest repo version: {new_latest_version}")
    if new_latest_version != latest_version:
        new_latest_tag_name = f"v{new_latest_version}"
        this_repo.create_tag(new_latest_tag_name)
        if args[PUSH_LONG_OPTION]:
            this_repo.remote().push(new_latest_tag_name)


if __name__ == "__main__":
    args = retrieve_cmd_args()
    main(args)
    sys.exit(0)
