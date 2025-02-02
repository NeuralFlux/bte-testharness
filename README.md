# bte-testharness
A lean CLI tool for testing BioThings Explorer derived from NCATS TestHarness.

### Usage
> [!IMPORTANT]
> The `suite` should be present in `<source-repo>/test_suites` folder.
```bash
pip install -r requirements.txt
pip install ARS_Test_Runner-0.1.9/
python main.py --url https://bte.ci.transltr.io/v1/query --suite sprint_4_tests
```


You may change the source of test cases and export detailed outputs using
```bash
python main.py --help
```

### Changes from TranslatorSRI/TestHarness
#### Major
1. Removed Reporter and Slacker API
2. Removed Smart API Registry scanner for various ARAs/ARS, now uses a single endpoint URL and infores
3. Updated `QueryRunner` to create queries for a single endpoint URL as opposed to multiple components and services
4. Removed ARS response formatting

#### Minor
1. Removed `pks` and `parent_pk` from `ResultCollector`
2. Removed all agents except for BTE from `ResultCollector`
3. Removed Benchmark Runner
4. Pass-Fail analysis is now done for empty results too
5. Pass-Fail analysis _does not_ sort results anymore (`ARS_Test_Runner`)

### To-do
- [ ] Update async methods to synchronous, if needed