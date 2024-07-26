"""Run tests through the Test Runners."""

import json
import logging
from typing import Dict

from ARS_Test_Runner.semantic_test import pass_fail_analysis
from tqdm import tqdm
from translator_testing_model.datamodel.pydanticmodel import TestCase

from result_collector import ResultCollector
from runner.query_runner import QueryRunner
from utils import hash_test_asset


async def run_tests(
    tests: Dict[str, TestCase],
    url: str,
    infores: str,
    logger: logging.Logger = logging.getLogger(__name__),
    **kwargs,
) -> Dict:
    """Send tests through the Test Runners."""
    logger.info(f"Running {len(tests)} tests...")
    full_report = {
        "PASSED": 0,
        "FAILED": 0,
        "SKIPPED": 0,
    }
    query_runner = QueryRunner(logger)
    collector = ResultCollector(logger)
    # loop over all tests
    for test in tqdm(tests.values()):
        status = "PASSED"
        # check if acceptance test
        if not test.test_assets or not test.test_case_objective:
            logger.warning(f"Test has missing required fields: {test.id}")
            continue

        query_responses = await query_runner.run_queries(test, url, infores)
        if test.test_case_objective == "AcceptanceTest":
            for asset in test.test_assets:
                # throw out any assets with unsupported expected outputs, i.e. OverlyGeneric
                if asset.expected_output not in collector.query_types:
                    logger.warning(
                        f"Asset id {asset.id} has unsupported expected output."
                    )
                    continue

                test_asset_hash = hash_test_asset(asset)
                test_query = query_responses.get(test_asset_hash)
                if test_query is None:
                    logger.warning("Unable to retrieve response for test asset.")

                if test_query is not None:
                    report = {
                        "pks": test_query["pks"],
                        "result": {},
                    }
                    for agent, response in test_query["responses"].items():
                        report["result"][agent] = {}
                        agent_report = report["result"][agent]
                        if response["status_code"] > 299:
                            agent_report["status"] = "FAILED"
                            if response["status_code"] == "598":
                                agent_report["message"] = "Timed out"
                            else:
                                agent_report["message"] = (
                                    f"Status code: {response['status_code']}"
                                )
                        # NOTE: `pass_fail_analysis` can handle empty results too
                        # elif (
                        #     response["response"]["message"]["results"] is None
                        #     or len(response["response"]["message"]["results"]) == 0
                        # ):
                        #     agent_report["status"] = "DONE"
                        #     agent_report["message"] = "No results"
                        else:
                            await pass_fail_analysis(
                                report["result"],
                                agent,
                                response["response"]["message"]["results"],
                                query_runner.normalized_curies[asset.output_id],
                                asset.expected_output,
                            )

                    status = (
                        report["result"]
                        .get("biothings-explorer", {})
                        .get("status", "SKIPPED")
                    )
                    full_report[status] += 1

                    collector.collect_result(test, asset, report["result"])
        elif test.test_case_objective == "QuantitativeTest":
            continue
        else:
            logger.error(f"Unsupported test type: {test.id}")
            status = "FAILED"
            full_report[status] += 1

        if kwargs["stats_json_path"] is not None:
            with open(kwargs["stats_json_path"], "w") as stats_fd:
                json.dump(collector.stats, stats_fd)

        if kwargs["report_csv_path"] is not None:
            with open(kwargs["report_csv_path"], "w") as csv_fd:
                csv_fd.write(collector.csv)

    return full_report
