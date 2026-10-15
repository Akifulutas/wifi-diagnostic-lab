"""Tests for wifi_lab doctor and CLI parsing."""

import unittest
from wifi_lab.doctor import check_python_version, check_os_platform, check_ping_tool
from wifi_lab.cli import build_parser


class TestDoctor(unittest.TestCase):
    def test_python_version_check(self):
        res = check_python_version()
        self.assertIn(res.status, ("OK", "FAIL"))
        self.assertEqual(res.name, "Python Runtime")

    def test_os_platform_check(self):
        res = check_os_platform()
        self.assertIn(res.status, ("OK", "WARN"))

    def test_ping_tool_check(self):
        res = check_ping_tool()
        self.assertIn(res.status, ("OK", "FAIL"))


class TestCLI(unittest.TestCase):
    def test_parser_subcommands(self):
        parser = build_parser()
        args = parser.parse_args(["doctor", "--verbose"])
        self.assertEqual(args.subcommand, "doctor")
        self.assertTrue(args.verbose)

        args = parser.parse_args(["collect", "--mock", "--runs", "3"])
        self.assertEqual(args.subcommand, "collect")
        self.assertTrue(args.mock)
        self.assertEqual(args.runs, 3)

        args = parser.parse_args(["analyse"])
        self.assertEqual(args.subcommand, "analyse")

        args = parser.parse_args(["suggest"])
        self.assertEqual(args.subcommand, "suggest")


if __name__ == "__main__":
    unittest.main()
