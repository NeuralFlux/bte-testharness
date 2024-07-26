"""Test ARS et all."""

import argparse
import asyncio
import datetime
import json
import logging
import os
import time
from copy import deepcopy
from typing import Any, Dict, List

import httpx
import requests

# We really shouldn't be doing this, but just for now...
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
logging.basicConfig(filename="test_ars.log", level=logging.DEBUG)

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
parser = argparse.ArgumentParser(description="Semantic Smoke Test")
parser.add_argument("--env", help="environment to run the analysis on", default="ci")
parser.add_argument("--predicate", help="predicate", default="treats", type=str)
parser.add_argument(
    "--runner_setting", help="creative mode indicator", nargs="*", type=str
)
parser.add_argument(
    "--expected_output",
    help="[TopAnswer'|'Acceptable'|'BadButForgivable'|'NeverShow']",
    nargs="*",
    type=str,
)
parser.add_argument(
    "--biolink_object_aspect_qualifier",
    help="activity_or_abundance",
    type=str,
    default="",
)
parser.add_argument(
    "--biolink_object_direction_qualifier",
    help="increased/decreased",
    type=str,
    default="",
)
parser.add_argument(
    "--input_category", help="Gene/Chemical", type=str, default="biolink:Disease"
)
parser.add_argument("--input_curie", help="Input Curie", type=str)
parser.add_argument("--output_curie", help="output Curie", nargs="*", type=str)

env_spec = {"dev": "ars-dev", "ci": "ars.ci", "test": "ars.test", "prod": "ars-prod"}


def get_safe(element, *keys):
    """
    :param element: JSON to be processed
    :param keys: list of keys in order to be traversed. e.g. "fields","data","message","results
    :return: the value of the terminal key if present or None if not
    """
    if element is None:
        return None
    _element = element
    for key in keys:
        try:
            _element = _element[key]
            if _element is None:
                return None
            if key == keys[-1]:
                return _element
        except KeyError:
            return None
    return None


def generate_message(
    predicate,
    creative,
    input_curie,
    biolink_object_aspect_qualifier,
    biolink_object_direction_qualifier,
    input_category,
):
    """Create a message to send to Translator services"""

    template_dir = BASE_PATH + "/templates"
    predicate_list = ["treats", "affects"]
    if predicate in predicate_list:
        if creative:
            template_name = predicate + "_creative"
        else:
            template_name = predicate
        with open(template_dir + f"/{template_name}.json") as f:
            template = json.load(f)
            # Fill message template with CURIEs
            query = deepcopy(template)
            nodes = get_safe(query, "message", "query_graph", "nodes")
            edges = get_safe(query, "message", "query_graph", "edges")
            if (
                biolink_object_aspect_qualifier == ""
                and biolink_object_direction_qualifier == ""
                and input_category == "biolink:Disease"
            ):
                for node_val in nodes.values():
                    if "ids" in node_val:
                        node_val["ids"].append(input_curie)
            else:
                if input_category == "biolink:Gene":
                    nodes["ON"]["ids"].append(input_curie)
                    del nodes["SN"]["ids"]
                    edges["t_edge"]["qualifier_constraints"][0]["qualifier_set"][0][
                        "qualifier_value"
                    ] = biolink_object_aspect_qualifier
                    edges["t_edge"]["qualifier_constraints"][0]["qualifier_set"][1][
                        "qualifier_value"
                    ] = biolink_object_direction_qualifier

                elif input_category == "biolink:ChemicalEntity":
                    nodes["SN"]["ids"].append(input_curie)
                    del nodes["ON"]["ids"]
                    edges["t_edge"]["qualifier_constraints"][0]["qualifier_set"][0][
                        "qualifier_value"
                    ] = biolink_object_aspect_qualifier
                    edges["t_edge"]["qualifier_constraints"][0]["qualifier_set"][1][
                        "qualifier_value"
                    ] = biolink_object_direction_qualifier
                else:
                    query = {
                        "error": f"unsupported input category provided: {input_category}"
                    }
    else:
        logging.error(f"Unknown Query predicate: {predicate}")
        query = {"error": f"unknow query predicate {predicate}"}
    return query


async def call_ars(payload: Dict[str, any], ARS_URL: str):
    url = ARS_URL + "submit"
    logging.debug("call_ars")

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url,
            json=payload,
            timeout=60,
        )
    response.raise_for_status()
    return response.json()


async def test_must_have_curie(
    ARS_URL: str,
    predicate: str,
    runner_setting,
    expected_output: List[str],
    biolink_object_aspect_qualifier: str,
    biolink_object_direction_qualifier: str,
    input_category: str,
    input_curie: str,
    output_curie: List[str],
    output_filename: str,
):
    """ " Send Concurrent async queries to ARS and get pass/fail report back"""

    if runner_setting == []:
        creative = False
    elif "inferred" in runner_setting:
        creative = True
    logging.debug(
        "Generating query message for %s in creative %s mode" % (input_curie, creative)
    )
    message = generate_message(
        predicate,
        creative,
        input_curie,
        biolink_object_aspect_qualifier,
        biolink_object_direction_qualifier,
        input_category,
    )
    logging.debug("query= " + json.dumps(message, indent=4, sort_keys=True))

    if "error" in message.keys():
        report_card = {}
        report_card["pks"] = {}
        report_card["results"] = [message] * len(expected_output)
    else:
        children, parent_pk = await get_children(message, ARS_URL, output_curie)
        if children[0][0] == "ars-default-agent" and "error" in children[0][1].keys():
            report_card = {}
            report_card["pks"] = {}
            report_card["results"] = []
            for child in children:
                if child[0] == "ars-default-agent":
                    report_card["pks"]["parent_pk"] = child[2]
                    report_card["results"].append(child[1])
                else:
                    report_card["pks"][child[0].split("-")[1]] = child[2]
                    report_card["results"].append(child[1])
        else:
            report_card = await ARS_semantic_analysis(
                children, parent_pk, output_curie, expected_output
            )

    return report_card


async def ARS_semantic_analysis(
    children: List[List], pk: str, output_curie: List[str], expected_output: List[str]
):
    """ " function to perform pass fail analysis on individual ARA's results"""
    report_card = {}
    report_card["pks"] = {}
    report_card["pks"]["parent_pk"] = pk
    report_card["results"] = []
    for idx, out_curie in enumerate(output_curie):
        if not out_curie:
            empty_mesg = {"error": "No output id is provided"}
            report_card["results"].append(empty_mesg)
            for data in children:
                infores = data[0]
                agent = infores.split("-")[1]
                child_pk = data[2]
                if infores.startswith("ar") and agent != "robokop":
                    report_card["pks"][agent] = child_pk
        else:
            expect_output = expected_output[idx]
            report = {}
            for data in children:
                infores = data[0]
                agent = infores.split("-")[1]
                child = data[1]
                child_pk = data[2]
                if infores.startswith("ar") and agent != "robokop":
                    report_card["pks"][agent] = child_pk
                    if isinstance(child["fields"]["data"], str) and (
                        child["fields"]["data"].startswith("Error_")
                        or child["fields"]["data"] == "merge_none"
                    ):
                        report[agent] = {}
                        if child["fields"]["data"].startswith("Error_"):
                            error_code = child["fields"]["data"].split("_")[1]
                            if child["fields"]["data"] == "Error_598":
                                report[agent]["status"] = "FAILED"
                                report[agent]["message"] = "Timed out"
                            else:
                                report[agent]["status"] = "FAILED"
                                report[agent]["message"] = f"Status code: {error_code}"
                        elif child["fields"]["data"] == "merge_none":
                            report[agent]["status"] = "FAILED"
                            report[agent]["message"] = "No results"
                    elif (
                        child["fields"]["data"] == "zero_results"
                        or child["fields"]["result_count"] == 0
                    ):
                        report[agent] = {}
                        report[agent]["status"] = "DONE"
                        report[agent]["message"] = "No results"
                    else:
                        results = get_safe(
                            child, "fields", "data", "message", "results"
                        )
                        if results is not None:
                            report[agent] = {}
                            report = await pass_fail_analysis(
                                report, agent, results, out_curie, expect_output
                            )

            report_card["results"].append(report)
    return report_card


async def pass_fail_analysis(
    report: Dict[str, any],
    agent: str,
    results: List[Dict[str, any]],
    out_curie: str,
    expect_output: str,
):
    """ " function to run pass fail analysis on individual results"""
    # get the top_n result's ids
    try:
        res_sort = results
        all_ids = []
        for res in res_sort:
            for _, res_value in res["node_bindings"].items():
                for val in res_value:
                    ids = str(val["id"])
                    if ids not in all_ids:
                        all_ids.append(ids)
        total_num_res = len(all_ids)
        if expect_output == "TopAnswer":
            if total_num_res <= 10:
                n_perc_res = res_sort[::]
            else:
                n_perc_res = res_sort[0 : int(len(res_sort) * (float(10) / 100))]
        elif expect_output == "Acceptable":
            n_perc_res = res_sort[0 : int(len(res_sort) * (float(50) / 100))]
        elif expect_output == "BadButForgivable":
            n_perc_res = res_sort[int(len(res_sort) * (float(50) / 100)) :]
        elif expect_output == "NeverShow":
            n_perc_res = res_sort
        else:
            error_mesg = {
                "error": "You have indicated a wrong category for expected output"
            }
            return error_mesg
        n_perc_ids = []
        for res in n_perc_res:
            for res_value in res["node_bindings"].values():
                for val in res_value:
                    ids = str(val["id"])
                    if ids not in n_perc_ids:
                        n_perc_ids.append(ids)
        # get the sugeno score & rank
        for idx, res in enumerate(results):
            node_bindings = get_safe(res, "node_bindings")
            for k in node_bindings.keys():
                nb = node_bindings[k]
                for c in nb:
                    the_id = get_safe(c, "id")
                if the_id == out_curie:
                    if "sugeno" in res.keys() and "rank" in res.keys():
                        ars_score = res["sugeno"]
                        ars_rank = res["rank"]
                        ara_score = None
                        ara_rank = None
                    else:
                        ars_score = None
                        ars_rank = None
                        for anal in res["analyses"]:
                            if "score" in anal.keys():
                                ara_score = anal["score"]
                            else:
                                ara_score = None
                        ara_rank = idx + 1

                    report[agent]["actual_output"] = {}
                    if ars_score is not None and ars_rank is not None:
                        report[agent]["actual_output"]["ars_score"] = ars_score
                        report[agent]["actual_output"]["ars_rank"] = ars_rank

                    if ara_score is not None and ara_rank is not None:
                        report[agent]["actual_output"]["ara_score"] = ara_score
                        report[agent]["actual_output"]["ara_rank"] = ara_rank

        if expect_output in ["TopAnswer", "Acceptable"]:
            if out_curie in n_perc_ids:
                report[agent]["status"] = "PASSED"
            elif out_curie not in n_perc_ids:
                if out_curie in all_ids:
                    report[agent]["status"] = "FAILED"
                else:
                    report[agent]["status"] = "FAILED"
                    report[agent]["actual_output"] = {}
                    if agent == "ars":
                        report[agent]["actual_output"]["ars_score"] = None
                        report[agent]["actual_output"]["ars_rank"] = None
                    else:
                        report[agent]["actual_output"]["ara_score"] = None
                        report[agent]["actual_output"]["ara_rank"] = None

        elif expect_output == "BadButForgivable":
            if out_curie in n_perc_ids:
                report[agent]["status"] = "PASSED"
            elif out_curie not in n_perc_ids and out_curie in all_ids:
                report[agent]["status"] = "FAILED"
            elif out_curie not in n_perc_ids and out_curie not in all_ids:
                report[agent]["status"] = "PASSED"
                report[agent]["actual_output"] = {}
                if agent == "ars":
                    report[agent]["actual_output"]["ars_score"] = None
                    report[agent]["actual_output"]["ars_rank"] = None
                else:
                    report[agent]["actual_output"]["ara_score"] = None
                    report[agent]["actual_output"]["ara_rank"] = None

        elif expect_output == "NeverShow":
            if out_curie in n_perc_ids:
                report[agent]["status"] = "FAILED"
            elif out_curie not in all_ids:
                report[agent]["status"] = "PASSED"
                report[agent]["actual_output"] = {}
                if agent == "ars":
                    report[agent]["actual_output"]["ars_score"] = None
                    report[agent]["actual_output"]["ars_rank"] = None
                else:
                    report[agent]["actual_output"]["ara_score"] = None
                    report[agent]["actual_output"]["ara_rank"] = None
    except Exception as e:
        report[agent]["status"] = "FAILED"
        report[agent]["message"] = f"An exception happened: {type(e), str(e)}"

    return report


async def get_children(query: Dict[str, Any], ARS_URL: str, output_curie, timeout=None):
    logging.debug("get_children")
    children = []
    response = await call_ars(query, ARS_URL)
    await asyncio.sleep(10)
    start_time = time.time()
    parent_pk = response["pk"]
    # print(f'starting to check for parent pk: {parent_pk}')
    logging.debug("parent_pk for query {}  is {} ".format(query, str(parent_pk)))
    url = ARS_URL + "messages/" + parent_pk + "?trace=y"
    if timeout is None:
        timeout = 60
    while (time.time() - start_time) / 60 < 15:
        # for 8 min, constantly check the parent status
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(url, timeout=timeout)
        try:
            data = r.json()
        except json.decoder.JSONDecodeError:
            logging.error("Non-JSON content received:")
            logging.error(r.text)

        if data["status"] == "Done":
            # print(f"finished processing message at: {(datetime.datetime.now()).strftime('%H:%M:%S')}")
            break
    else:
        logging.debug(
            f"Parent pk: {parent_pk} is still 'Running' even after 8 min, please check the timeout operation"
        )
        children.append(
            ["ars-default-agent", {"error": "ARS still Running"}, parent_pk]
        )
        for child in data["children"]:
            agent = child["actor"]["agent"]
            child_pk = child["message"]
            if agent.startswith("ar"):
                children.append([agent, {"error": "ARS still Running"}, child_pk])
        return children, parent_pk

    if data is not None:
        for child in data["children"]:
            agent = child["actor"]["agent"]
            childPk = child["message"]
            logging.debug("---Checking child for " + agent + ", pk=" + parent_pk)
            childData = await get_child(childPk, ARS_URL, output_curie)
            if childData is None:
                pass
            else:
                # append each child with its results
                children.append([agent, childData, childPk])
    if data["merged_version"] == "None":
        children.append(["ars-ars-agent", {"fields": {"data": "merge_none"}}, None])

    return children, parent_pk


async def get_merged_data(ARS_URL: str, merged_pk: str, time_out):
    """function to retrieve completed merged data"""
    wait_time = 10
    merged_url = ARS_URL + "messages/" + merged_pk
    async with httpx.AsyncClient(verify=False) as client:
        rr = await client.get(
            merged_url,
            timeout=60,
        )
    rr.raise_for_status()
    merged_data = rr.json()
    status = get_safe(merged_data, "fields", "status")
    if status is not None:
        if status == "Done":
            return merged_data
        elif status == "Running":
            if time_out > 0:
                logging.debug(
                    "Query merged response is still running\n"
                    + "Wait time remaining is now "
                    + str(time_out)
                    + "\n"
                    + "What we have so far is: "
                    + json.dumps(merged_data, indent=4, sort_keys=True)
                )
                await asyncio.sleep(wait_time)
                remaining_time = time_out - wait_time
                # print(f'going to try getting merged_data for remaining time of {remaining_time}')
                return await get_merged_data(ARS_URL, merged_pk, remaining_time)
        else:
            # print(f"even after timeout {merged_pk} is still Running, Returning None")
            logging.debug(
                "even after timeout" + merged_pk + "is still Running"
            )  # sorry bud, time's up
            return None


async def get_child(pk: str, ARS_URL: str, output_curie, timeout=60):
    logging.debug("get_child(" + pk + ")")
    wait_time = (
        10  # amount of seconds to wait between checks for a Running query result
    )
    url = ARS_URL + "messages/" + pk
    async with httpx.AsyncClient(verify=False) as client:
        child_response = await client.get(url, timeout=60.0)
    data = child_response.json()
    # with open(f'{pk}_response.json', "w") as f:
    #      json.dump(data, f, indent=4)

    status = get_safe(data, "fields", "status")
    code = get_safe(data, "fields", "code")
    result_count = get_safe(data, "fields", "result_count")
    if status is not None:
        if status == "Done":
            if result_count is None:
                data = {"fields": {"data": "zero_results"}}
            elif result_count >= 0:
                logging.debug(
                    "get_child for " + pk + "returned" + str(result_count) + " results"
                )
            return data
        elif status == "Error" or status == "Unknown":
            logging.debug("Errored out")
            data = {"fields": {"data": f"Error_{code}"}}
            return data
        elif status == "Running":
            if timeout > 0:
                logging.debug(
                    "Query response is still running\n"
                    + "Wait time remaining is now "
                    + str(timeout)
                    + "\n"
                    + "What we have so far is: "
                    + json.dumps(data, indent=4, sort_keys=True)
                )
                await asyncio.sleep(wait_time)
                return await get_child(pk, ARS_URL, timeout - wait_time)
            else:
                logging.debug(
                    "even after timeout" + pk + "is still Running"
                )  # sorry bud, time's up
                return None
        else:
            # status must be some manner of error
            logging.debug(
                "Error status found in get_child for "
                + pk
                + "\n"
                + "Status is "
                + status
                + "\n"
                + json.dumps(data, indent=4, sort_keys=True)
            )
            return None
    else:
        # Should I be throwing an exception here instead?
        logging.error("Status in get_child for " + pk + " was no retrievable")
        logging.error(json.dumps(data, indent=4, sort_keys=True))
    # We shouldn't get here
    logging.error("Error in get_child for \n" + pk + "\n No child retrievable")
    return None


async def run_semantic_test(
    env: str,
    predicate: str,
    runner_setting: List[str],
    expected_output: List[str],
    biolink_object_aspect_qualifier: str,
    biolink_object_direction_qualifier: str,
    input_category: str,
    input_curie: List[str],
    output_curie: List[str],
):
    ars_env = env_spec[env]
    ARS_URL = f"https://{ars_env}.transltr.io/ars/api/"
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    output_filename = f"ARS_smoke_test_{timestamp}.json"
    report_card = await test_must_have_curie(
        ARS_URL,
        predicate,
        runner_setting,
        expected_output,
        biolink_object_aspect_qualifier,
        biolink_object_direction_qualifier,
        input_category,
        input_curie,
        output_curie,
        output_filename,
    )
    return report_card, ARS_URL


if __name__ == "__main__":

    args = parser.parse_args()
    env = getattr(args, "env")
    predicate = getattr(args, "predicate")
    runner_setting = getattr(args, "runner_setting")
    expected_output = getattr(args, "expected_output")
    biolink_object_aspect_qualifier = getattr(args, "biolink_object_aspect_qualifier")
    biolink_object_direction_qualifier = getattr(
        args, "biolink_object_direction_qualifier"
    )
    input_category = getattr(args, "input_category")
    input_curie = getattr(args, "input_curie")
    output_curie = getattr(args, "output_curie")

    current_time = datetime.datetime.now()
    formatted_start_time = current_time.strftime("%H:%M:%S")
    print(f"started performing ARS_Test pass/fail Analysis at {formatted_start_time}")
    print(
        asyncio.run(
            run_semantic_test(
                env,
                predicate,
                runner_setting,
                expected_output,
                biolink_object_aspect_qualifier,
                biolink_object_direction_qualifier,
                input_category,
                input_curie,
                output_curie,
            )
        )
    )
    endtime = datetime.datetime.now()
    formatted_end_time = endtime.strftime("%H:%M:%S")
    print(f"finished running the analysis at {formatted_end_time}")
