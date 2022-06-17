"""Tests most Makefile targets."""
# Standard Library Imports
import os
import subprocess
import sys
import time
import unittest

# Third Party Imports

# Local Application Imports

# constants and other program configurations
DOCKER_TEST_IMAGE = f"{os.environ['DOCKER_REPO']}:test"


class TestLintTarget(unittest.TestCase):
    """Run the lint Makefile target."""

    def test_ansible_lint_target(self):
        """Run the lint Makefile target."""
        mkprocess = subprocess.run(
            ("make", "lint"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)


class TestImageTarget(unittest.TestCase):
    """Run the image Makefile target."""

    def test_image_target(self):
        """Run the image Makefile target."""
        mkprocess = subprocess.run(
            ("make", "image"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)


class TestImageTargetDoesImageExist(unittest.TestCase):
    """Check if test image exists after running target."""

    def setUp(self):
        """Set up environment before running test method(s)."""
        mkprocess = subprocess.run(
            ("make", "image"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

    def test_image_target_does_image_exist(self):
        """Check if test image exists in Docker's cache."""
        docker_process = subprocess.run(
            (
                "docker",
                "images",
                "--quiet",
                DOCKER_TEST_IMAGE,
            ),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertNotEqual(
            docker_process.stdout, "", f"Could not find {DOCKER_TEST_IMAGE}"
        )


class TestDeployTarget(unittest.TestCase):
    """Run the deploy Makefile target."""

    def setUp(self):
        """Set up environment before running test method(s)."""
        mkprocess = subprocess.run(
            ("make", "image"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

    def test_deploy_target(self):
        """Run the deploy Makefile target."""
        mkprocess = subprocess.run(
            ("make", "deploy"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)


class TestDeployTargetIsContainerRunning(unittest.TestCase):
    """Ensure test deployment is successful after running target."""

    def setUp(self):
        """Set up environment before running test method(s)."""
        mkprocess = subprocess.run(
            ("make", "image"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

        mkprocess = subprocess.run(
            ("make", "deploy"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

    def test_deploy_target_container_running(self):
        """Ensure test deployment is successful after running target."""
        # give time for Jenkins to spin up
        time.sleep(30)

        docker_process = subprocess.run(
            (
                "docker",
                "container",
                "inspect",
                os.environ["CONTAINER_NAME"],
                "--format",
                "{{ .State.ExitCode }}",
            ),
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
        self.assertEqual(
            docker_process.stdout.strip(),
            "0",
            f"Container exit code: {docker_process.stdout}",
        )


class TestDismantleTarget(unittest.TestCase):
    """Run the dismantle Makefile target."""

    def setUp(self):
        """Set up environment before running test method(s)."""
        mkprocess = subprocess.run(
            ("make", "image"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

        mkprocess = subprocess.run(
            ("make", "deploy"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

    def test_dismantle(self):
        """Run the dismantle Makefile target."""
        mkprocess = subprocess.run(
            ("make", "dismantle"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)


class TestCleanTarget(unittest.TestCase):
    """Run the clean Makefile target."""

    def setUp(self):
        """Set up environment before running test method(s)."""
        mkprocess = subprocess.run(
            ("make", "image"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

    def test_clean(self):
        """Run the clean Makefile target."""
        mkprocess = subprocess.run(
            ("make", "clean"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)


class TestCleanTargetDoesImageNotExist(unittest.TestCase):
    """Check if test image does not exist after running the clean target."""

    def setUp(self):
        """Set up environment before running test method(s)."""
        mkprocess = subprocess.run(
            ("make", "clean"),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(mkprocess.returncode, 0, mkprocess.stderr)

    def test_clean_target_does_image_not_exist(self):
        """Check if test image does not exist."""
        docker_process = subprocess.run(
            (
                "docker",
                "images",
                "--quiet",
                DOCKER_TEST_IMAGE,
            ),
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(
            docker_process.stdout,
            "",
            f"Test image still exists: {DOCKER_TEST_IMAGE}",
        )


if __name__ == "__main__":
    unittest.main()
    sys.exit(0)
