"""Translator Test Query Runner."""

import asyncio
import logging
from typing import Dict, Tuple

import httpx
from translator_testing_model.datamodel.pydanticmodel import TestCase

from runner.generate_query import generate_query
from utils import hash_test_asset, normalize_curies

MAX_QUERY_TIME = 600
MAX_ARA_TIME = 360

env_map = {
    "dev": "development",
    "ci": "staging",
    "test": "testing",
    "prod": "production",
}


class QueryRunner:
    """Translator Test Query Runner."""

    def __init__(self, logger: logging.Logger):
        self.normalized_curies = {}
        self.logger = logger

    async def run_query(
        self, query_hash, semaphore, message, url, infores
    ) -> Tuple[int, Dict[str, dict], Dict[str, str]]:
        """Generate and run a single TRAPI query against a component."""
        # wait for opening in semaphore before sending next query
        responses = {}
        pks = {}
        async with semaphore:
            # send message
            response = {}
            status_code = 418
            async with httpx.AsyncClient(timeout=600) as client:
                try:
                    res = await client.post(url, json=message)
                    status_code = res.status_code
                    res.raise_for_status()
                    response = res.json()
                except Exception as e:
                    self.logger.error(f"Something went wrong: {e}")

            single_infores = infores.split("infores:")[1]
            # TODO: normalize this response
            responses[single_infores] = {
                "response": response,
                "status_code": status_code,
            }

        return query_hash, responses, pks

    async def run_queries(
        self,
        test_case: TestCase,
        url: str,
        infores: str,
        concurrency: int = 1,  # for performance testing
    ) -> Dict[int, dict]:
        """Run all queries specified in a Test Case."""
        # normalize all the curies in a test case
        self.normalized_curies.update(await normalize_curies(test_case, self.logger))
        # TODO: figure out the right way to handle input category wrt normalization

        queries: Dict[int, dict] = {}
        for test_asset in test_case.test_assets:
            test_asset.input_id = self.normalized_curies[test_asset.input_id]
            # TODO: make this better
            asset_hash = hash_test_asset(test_asset)
            if asset_hash not in queries:
                # generate query
                query = generate_query(test_asset)
                queries[asset_hash] = {
                    "query": query,
                    "responses": {},
                    "pks": {},
                }

        self.logger.debug(queries)
        # send queries to a single type of component at a time
        tasks = []
        for query_hash, query in queries.items():
            # component = "ara"
            # loop over all specified components, i.e. ars, ara, kp, utilities
            semaphore = asyncio.Semaphore(concurrency)
            self.logger.info(f"Sending queries to {url}")
            tasks.append(
                asyncio.create_task(
                    self.run_query(
                        query_hash,
                        semaphore,
                        query["query"],
                        url,
                        infores,
                    )
                )
            )
        try:
            all_responses = await asyncio.gather(*tasks, return_exceptions=True)
            for query_hash, responses, pks in all_responses:
                queries[query_hash]["responses"].update(responses)
                queries[query_hash]["pks"].update(pks)
        except Exception as e:
            self.logger.error(f"Something went wrong with the queries: {e}")

        return queries
