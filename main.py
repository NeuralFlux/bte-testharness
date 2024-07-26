import json
from asyncio import run as aiorun
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import httpx
import typer
from translator_testing_model.datamodel.pydanticmodel import TestSuite
from typing_extensions import Annotated

from logger import get_logger, setup_logger
from run import run_tests

setup_logger()


def download(suite: str, test_repo: str) -> dict[str, Any]:
    download_url = f"https://raw.githubusercontent.com/{test_repo}/main/test_suites/"
    with httpx.Client(timeout=None) as client:
        file = client.get(f"{download_url}{suite}.json")
        file.raise_for_status()
        return file.json()


app = typer.Typer()


@app.command()
def main(
    url: Annotated[
        str,
        typer.Option(help="The URL of the ARA to run tests against.", prompt=True),
    ],
    suite: Annotated[
        str,
        typer.Option(
            help="The name/id of the suite to be run. NOTE: must be in folder `test_suites` of the repo.",
        ),
    ],
    summary_json_path: Annotated[
        str,
        typer.Option(help="The path to write the output summary.", prompt=True),
    ] = "test-results.json",
    test_repo: Annotated[
        Optional[str],
        typer.Option(help="The source of test cases. `<user>/<repo-name>`"),
    ] = "NCATSTranslator/Tests",
    infores: Annotated[
        Optional[str],
        typer.Option(
            help="The infores of ARA to run tests against.",
        ),
    ] = "infores:biothings-explorer",
    stats_json_path: Annotated[
        Optional[str],
        typer.Option(
            help="The path to write the detailed stats JSON.",
        ),
    ] = None,
    report_csv_path: Annotated[
        Optional[str],
        typer.Option(
            help="The path to write the detailed CSV report.",
        ),
    ] = None,
    log_level: Annotated[
        Optional[str],
        typer.Option(
            help="Level of logs to print.",
            show_choices=["ERROR", "WARNING", "INFO", "DEBUG"],
        ),
    ] = "WARNING",
):

    # use async method since queries are run asynchronously
    async def _main():
        tests = TestSuite.model_validate(download(suite, test_repo)).test_cases
        qid = str(uuid4())[:8]
        logger = get_logger(qid, log_level)

        if len(tests) < 1:
            return logger.warning("No tests to run. Exiting.")

        report = await run_tests(
            tests=tests,
            url=url,
            infores=infores,
            logger=logger,
            stats_json_path=stats_json_path,
            report_csv_path=report_csv_path,
        )

        logger.info("Finishing up test run...")

        if summary_json_path is not None:
            logger.info("Saving report as JSON...")
            with open(summary_json_path, "w") as f:
                json.dump(report, f)

        logger.info("All tests have completed!")

    aiorun(_main())


if __name__ == "__main__":
    app()
