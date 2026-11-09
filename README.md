# Jailbreak the Vault entry

A deterministic, model free agent for jailbreak-the-vault-01. It asks for a six line labelled word encoding, parses evidence from the reply, then submits supported guesses through the trial environment.

## Mock tests

Run the unit and integration suites with:

~~~sh
python3 -m unittest discover -s tests
python3 tests/run_mock_trials.py --kit /home/hatch/workspace/makefun-kit/jailbreak-the-vault-01-kit
~~~

The batch starts the kit's real environment and scorer with a local mock target lane. Its generated tests/mock_results.json is a build artifact.

## Harness

The make.fun harness runs main.py in the trial sandbox with MAKEFUN_ENV_URL and MAKEFUN_PROMPT_FILE set. The agent talks only to that environment's /chat and /guess routes.
