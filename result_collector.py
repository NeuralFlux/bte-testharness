"""The Collector of Results."""

import logging

from translator_testing_model.datamodel.pydanticmodel import TestAsset, TestCase

from utils import get_tag


class ResultCollector:
    """Collect results for easy dissemination."""

    def __init__(self, logger: logging.Logger):
        """Initialize the Collector."""
        self.logger = logger
        self.agents = [
            "biothings-explorer",
        ]
        self.query_types = ["TopAnswer", "Acceptable", "BadButForgivable", "NeverShow"]
        self.result_types = {
            "PASSED": "PASSED",
            "FAILED": "FAILED",
            "No results": "No results",
            "-": "Test Error",
        }
        self.stats = {}
        for agent in self.agents:
            self.stats[agent] = {}
            for query_type in self.query_types:
                self.stats[agent][query_type] = {}
                for result_type in self.result_types.values():
                    self.stats[agent][query_type][result_type] = 0

        self.columns = ["name", "TestCase", "TestAsset", *self.agents]
        header = ",".join(self.columns)
        self.csv = f"{header}\n"

    def collect_result(
        self,
        test: TestCase,
        asset: TestAsset,
        report: dict,
    ):
        """Add a single report to the total output."""
        # add result to stats
        for agent in self.agents:
            query_type = asset.expected_output
            if agent in report:
                result_type = self.result_types.get(
                    get_tag(report[agent]), "Test Error"
                )
                if (
                    query_type in self.stats[agent]
                    and result_type in self.stats[agent][query_type]
                ):
                    self.stats[agent][query_type][result_type] += 1
                else:
                    self.logger.error(
                        f"Got {query_type} and {result_type} and can't put into stats!"
                    )

        # add result to csv
        agent_results = ",".join(
            get_tag(report[agent]) for agent in self.agents if agent in report
        )
        self.csv += f"""{asset.name},{test.id},{asset.id},{agent_results}\n"""
