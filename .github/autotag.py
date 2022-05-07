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


class VersionUpdateTypes(enum.Enum):
    """Represent values that designate type of software versioning update."""

    MAJOR = enum.auto()
    MINOR = enum.auto()
    PATCH = enum.auto()


class Version:
    """Represent a generic software version."""

    @classmethod
    def determine_greatest_update_type(self, versions):
        """Determine the greatest version update type passed in.

        Parameters
        ----------
        versions : list of autotag.VersionUpdateTypes
            A list of VersionUpdateTypes objects.

        Returns
        -------
        autotag.VersionUpdateTypes or None
            The greatest update type, or None if versions is empty.

        """
        greatest = None

        # major > minor > patch
        for version in versions:
            if version == VersionUpdateTypes.PATCH and (
                greatest != VersionUpdateTypes.MINOR
                and greatest  # noqa: W503
                != VersionUpdateTypes.MAJOR  # noqa: W503
            ):
                greatest = VersionUpdateTypes.PATCH
            elif version == VersionUpdateTypes.MINOR and (
                greatest != VersionUpdateTypes.MAJOR
            ):
                greatest = VersionUpdateTypes.MINOR
            elif version == VersionUpdateTypes.MAJOR:
                greatest = VersionUpdateTypes.MAJOR

        return greatest

    def determine_update_types(self, v1):
        """Determine the version update types between another version.

        Parameters
        ----------
        v1 : autotag.Version
            A version object.

        Returns
        -------
        list of autotag.VersionUpdateTypes

        Notes
        -----
        When going from one (software) version to another. It's normal to
        consider whether the new version is considered a patch, minor, or major
        update to the previous version.

        """
        update_types = list()
        if abs(self.major - v1.major) > 0:
            update_types.append(VersionUpdateTypes.MAJOR)
        if abs(self.minor - v1.minor) > 0:
            update_types.append(VersionUpdateTypes.MINOR)
        if abs(self.patch - v1.patch) > 0:
            update_types.append(VersionUpdateTypes.PATCH)

        return update_types


class SemanticVersion(Version):
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

    def set_major(self, to):
        """Set the semantic versioning major to a given version.

        Parameters
        ----------
        to : int
            The version to set the semantic versioning major to.

        """
        self.major = to
    
    def set_minor(self, to):
        """Set the semantic versioning minor to a given version.

        Parameters
        ----------
        to : int
            The version to set the semantic versioning minor to.

        """
        self.minor = to

    def set_patch(self, to):
        """Set the semantic versioning patch to a given version.

        Parameters
        ----------
        to : int
            The version to set the semantic versioning patch to.

        """
        self.patch = to

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


class JenkinsVersion(Version):
    """Represent a jenkins version.

    Parameters
    ----------
    version : str
        A jenkins version string (e.g. 1.2.3, 3.2.2).

    Attributes
    ----------
    JENKINS_VERSION_REGEX : str
        The regex used to extract the different parts of the jenkins
        versioning.

    """

    _MAJOR_CAPTURE_GROUP = 1
    _MINOR_CAPTURE_GROUP = 2
    _PATCH_CAPTURE_GROUP = 3
    _IMPLICIT_PATCH_CHANGE_VERSION = -1

    # based on the semantic version regex
    JENKINS_VERSION_REGEX = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"  # noqa: E501

    def __init__(self, version):
        """Construct the jenkins version object."""
        version_groups = re.match(self.JENKINS_VERSION_REGEX, version)
        self.major = int(version_groups[self._MAJOR_CAPTURE_GROUP])
        self.minor = int(version_groups[self._MINOR_CAPTURE_GROUP])
        self.patch = version_groups[self._PATCH_CAPTURE_GROUP]

        if not self.patch:
            # I still want to always detect a patch version update regardless
            # of what this version ever gets compared to. This is unless only
            # a minor to minor version update occurs (e.g. 2.333 -> 2.334).
            self.patch = self._IMPLICIT_PATCH_CHANGE_VERSION
        else:
            self.patch = int(self.patch)

    def __eq__(self, v):
        """Determine if the jenkins version is equal to this instance."""
        return (
            f"{self.major}.{self.minor}.{self.patch}"
            == f"{v.major}.{v.minor}.{v.patch}"  # noqa: W503
        )

    def __str__(self):
        """Return the string representation of an instance."""
        return (
            f"{self.major}.{self.minor}"
            if self.patch == self._IMPLICIT_PATCH_CHANGE_VERSION
            else f"{self.major}.{self.minor}.{self.patch}"
        )


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

    repo_update_types = list()
    reseat_latest_version_tag = False
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
            prior_jenkins_version = JenkinsVersion(
                get_jenkins_version(docker_client, prior_jenkins_img)
            )
            current_jenkins_version = JenkinsVersion(
                get_jenkins_version(docker_client, current_jenkins_img)
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
                Version.determine_greatest_update_type(types_of_jenkins_update)
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
            reseat_latest_version_tag = True

    greatest_repo_update_type = Version.determine_greatest_update_type(
        repo_update_types
    )
    if greatest_repo_update_type == VersionUpdateTypes.PATCH:
        new_latest_version.increment_patch(1)
    elif greatest_repo_update_type == VersionUpdateTypes.MINOR:
        new_latest_version.set_patch(0)
        new_latest_version.increment_minor(1)
    elif greatest_repo_update_type == VersionUpdateTypes.MAJOR:
        new_latest_version.set_patch(0)
        new_latest_version.set_minor(0)
        new_latest_version.increment_major(1)

    _logger.info(f"the prior latest repo version: {latest_version}")
    _logger.info(f"the final new latest repo version: {new_latest_version}")
    if new_latest_version != latest_version:
        new_latest_tag_name = f"v{new_latest_version}"
        this_repo.create_tag(new_latest_tag_name)
        if args[PUSH_LONG_OPTION]:
            this_repo.remote().push(new_latest_tag_name)
    elif reseat_latest_version_tag:
        latest_tag_name = f"v{latest_version}"
        short_head_hash = str(this_repo.head.commit)[:8]
        _logger.info(
            f"reset {latest_tag_name} to commit -> {short_head_hash}"
        )
        this_repo.delete_tag(latest_tag_name)
        this_repo.create_tag(latest_tag_name)
        if args[PUSH_LONG_OPTION]:
            # According to the git-push man page, the equivalent of using
            # 'git push --delete <remote> <tag>' would be to append the tag
            # name with a colon character.
            this_repo.remote().push(f":{latest_tag_name}")
            this_repo.remote().push(latest_tag_name)


if __name__ == "__main__":
    args = retrieve_cmd_args()
    main(args)
    sys.exit(0)
