
Translator ARS Pass/Fail Testing 
==========================================================

This testing framework performs single level pass/Fail analysis on queries it receives from the Test Runner. 

### ARS_Test Implementation
```bash
pip install ARS_Test_Runner 
```

### CLI
The command-line interface is the easiest way to run the ARS_Test_Runner
After installation, simply type ARS_Test_Runner --help to see required input arguments & options
- `ARS_Test_Runner`
    - env : the environment to run the queries against (dev|ci|test|prod)
    - predicate: treats
    - runner_setting: creative mode inidicator (inferred)
    - expected_output: TopAnswer|Acceptable|BadButForgivable|NeverShow
    - biolink_object_aspect_qualifier: activity_or_abundance
    - biolink_object_direction_qualifier: increased/decreased
    - input_category: input type category (Gene/Chemical)
    - input_curie: normalized curie taken from assest.csv
    - output_curie: target output curie to do analysis on

- example:
  - for single output (mvp2)
    - ARS_Test_Runner --env 'test' --predicate 'affects' --runner_setting '["inferred"]'  --expected_output '["TopAnswer"]'  --biolink_object_aspect_qualifier 'activity_or_abundance' --biolink_object_direction_qualifier 'increased' --input_category 'biolink:Gene' --input_curie 'NCBIGene:23394' --output_curie '["PUBCHEM.COMPOUND:3821"]'
  - for multi outputs (mvp1)
    - ARS_Test_Runner --env 'ci' --predicate 'treats' --runner_setting '["inferred"]' --expected_output '["TopAnswer","TopAnswer"]' --input_category 'biolink:Disease' --input_curie 'MONDO:0005301' --output_curie '["PUBCHEM.COMPOUND:107970","UNII:3JB47N2Q2P"]'


### python
``` python 
import asyncio
from ARS_Test_Runner.semantic_test import run_semantic_test
asyncio.run(run_semantic_test('ci','treats',['inferred'], ['TopAnswer','TopAnswer'],'','','biolink:Disease', 'MONDO:0005301',['PUBCHEM.COMPOUND:107970','UNII:3JB47N2Q2P']))
asyncio.run(run_semantic_test('ci','affects',['inferred'], ['TopAnswer'],'activity_or_abundance','increased','biolink:Gene' ,'NCBIGene:23394',['PUBCHEM.COMPOUND:3821']))
```
OR
``` python 
python semantic_test.py --env 'ci' --predicate 'treats' --runner_setting 'inferred' --expected_output 'TopAnswer' 'TopAnswer' --input_category 'biolink:Disease' --input_curie 'MONDO:0005301' --output_curie 'PUBCHEM.COMPOUND:107970' 'UNI:3JB47N2Q2P'
python semantic_test.py --env 'ci' --predicate 'affects' --runner_setting 'inferred' --expected_output 'TopAnswer' --biolink_object_aspect_qualifier 'activity_or_abundance' --biolink_object_direction_qualifier 'increased' --input_category 'biolink:Gene' --input_curie 'NCBIGene:23394' --output_curie 'PUBCHEM.COMPOUND:3821'
```






