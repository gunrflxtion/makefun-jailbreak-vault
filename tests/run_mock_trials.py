#!/usr/bin/env python3
"""Run the agent against the kit's REAL env and scorer, with a mock target.

For each practice trial and each mock-house-lane profile this starts:
  1. tests/mock_house_lane.py  (the target model, one profile)
  2. the kit's program/env/server.mjs, pointed at the trial's input/env
     and at the mock lane as its house lane
  3. main.py, pointed at that env
then SIGTERMs the env (it exports state.json), scores the export with the
kit's program/scorer/score.mjs, and records the result.

The only simulated part is the target model's text: the env (turns,
guesses, chars, redaction filters, state export) and the scorer are the
kit's own code, byte for byte.

Usage:
  python3 tests/run_mock_trials.py --kit ./kit/jailbreak-the-vault-01-kit
  python3 tests/run_mock_trials.py --kit <kit> --trials 0 1 --profiles compliant guarded

Results are printed as a table and written to tests/mock_results.json.
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

BASELINE = 86600
PROFILES = ("compliant", "guarded", "nato-only", "sloppy", "partial",
            "refuse-all")


def free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def wait_http(url, timeout_s=20):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def wait_file(path, timeout_s=20):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if os.path.exists(path):
            return True
        time.sleep(0.2)
    return False


def run_one(kit_dir, repo_dir, trial, profile, trial_dir=None):
    if trial_dir is None:
        trial_dir = os.path.join(kit_dir, "practice", "trial-%d" % trial)
    with open(os.path.join(trial_dir, "reference", "answer.json")) as fh:
        answer = json.load(fh)
    secrets = [s["secret"] for s in answer["stages"]]
    tmp = tempfile.mkdtemp(prefix="mocktrial-%s-%s-" % (trial, profile))
    state_dir = os.path.join(tmp, "state")
    os.makedirs(state_dir)
    lane_port = free_port()
    env_port = free_port()
    lane_url = "http://127.0.0.1:%d" % lane_port
    env_url = "http://127.0.0.1:%d" % env_port

    lane = subprocess.Popen(
        [sys.executable,
         os.path.join(repo_dir, "tests", "mock_house_lane.py"),
         "--profile", profile, "--port", str(lane_port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = {"trial": trial, "profile": profile, "secrets": secrets,
              "points": None, "levels": None, "solved": None, "turns": None,
              "stages": None, "agent_exit": None, "agent_output": "",
              "error": None}
    try:
        if not wait_http(lane_url + "/", timeout_s=15):
            result["error"] = "mock lane did not come up"
            return result
        env_env = dict(os.environ)
        env_env.update({
            "MAKEFUN_ENV_DATA_DIR": os.path.join(trial_dir, "input", "env"),
            "MAKEFUN_STATE_DIR": state_dir,
            "MAKEFUN_HOUSE_LLM_URL": lane_url,
            "MAKEFUN_HOUSE_TOKEN": "mock-token",
            "MAKEFUN_ENV_PORT": str(env_port),
            "MAKEFUN_ENV_HOST": "127.0.0.1",
        })
        env = subprocess.Popen(
            ["node", os.path.join(kit_dir, "program", "env", "server.mjs")],
            env=env_env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        try:
            if not wait_file(os.path.join(state_dir, "ready"),
                             timeout_s=20):
                result["error"] = "env did not write its ready file"
                return result
            agent_env = dict(os.environ)
            agent_env.update({
                "MAKEFUN_PROMPT_FILE": os.path.join(
                    trial_dir, "input", "prompt.txt"),
                "MAKEFUN_ENV_URL": env_url,
                "MAKEFUN_TRIAL_SEED": "mock-seed-%s-%s" % (trial, profile),
                "MAKEFUN_TRIAL_NOW": "2026-11-09T00:00:00.000Z",
            })
            try:
                proc = subprocess.run(
                    [sys.executable, os.path.join(repo_dir, "main.py")],
                    env=agent_env, cwd=repo_dir, capture_output=True,
                    text=True, timeout=600)
                result["agent_exit"] = proc.returncode
                result["agent_output"] = (proc.stdout + proc.stderr)[-2000:]
            except subprocess.TimeoutExpired:
                result["error"] = "main.py timed out after 600s"
                return result
        finally:
            env.send_signal(signal.SIGTERM)
            try:
                env.wait(timeout=15)
            except subprocess.TimeoutExpired:
                env.kill()
                env.wait()
        state_path = os.path.join(state_dir, "export", "state.json")
        if not os.path.exists(state_path):
            result["error"] = "env exported no state.json"
            return result
        with open(state_path) as fh:
            state = json.load(fh)
        scores_dir = os.path.join(tmp, "scores")
        os.makedirs(scores_dir)
        score_env = dict(os.environ)
        score_env.update({
            "MAKEFUN_OUTPUT_DIR": os.path.join(state_dir, "export"),
            "MAKEFUN_REFERENCE_DIR": os.path.join(trial_dir, "reference"),
            "MAKEFUN_SCORES_DIR": scores_dir,
        })
        proc = subprocess.run(
            ["node", os.path.join(kit_dir, "program", "scorer", "score.mjs")],
            env=score_env, capture_output=True, text=True, timeout=60)
        scores_path = os.path.join(scores_dir, "scores.json")
        if not os.path.exists(scores_path):
            result["error"] = "scorer failed: " + (proc.stdout + proc.stderr)[-500:]
            return result
        with open(scores_path) as fh:
            scores = json.load(fh)
        result.update({
            "points": scores["points"],
            "levels": scores["levels"],
            "solved": scores["solved"],
            "turns": scores["turns"],
            "stages": state["stages"],
            "redactions": state["redactions"],
            "guesses": state["guesses"],
        })
        return result
    finally:
        lane.send_signal(signal.SIGTERM)
        try:
            lane.wait(timeout=10)
        except subprocess.TimeoutExpired:
            lane.kill()
            lane.wait()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kit", required=True,
                    help="path to the unpacked competition kit")
    ap.add_argument("--trials", type=int, nargs="*", default=[0, 1, 2])
    ap.add_argument("--trial-dir", default=None,
                    help="run one ad-hoc trial from this directory "
                         "(input/env/target.json, input/prompt.txt, "
                         "reference/answer.json) instead of --trials")
    ap.add_argument("--profiles", nargs="*", default=list(PROFILES))
    ap.add_argument("--out", default=None,
                    help="results JSON path (default tests/mock_results.json)")
    args = ap.parse_args()
    kit_dir = os.path.abspath(args.kit)
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if not os.path.isdir(os.path.join(kit_dir, "program", "env")):
        print("kit not found at %s (want program/env under it)"
              % kit_dir, file=sys.stderr)
        return 2
    results = []
    if args.trial_dir:
        label = os.path.basename(os.path.abspath(args.trial_dir.rstrip("/")))
        for profile in args.profiles:
            print("trial %s profile %-11s ... " % (label, profile),
                  end="", flush=True)
            res = run_one(kit_dir, repo_dir, label, profile,
                          trial_dir=args.trial_dir)
            results.append(res)
            if res["error"]:
                print("ERROR %s" % res["error"], flush=True)
            else:
                print("points %5d levels %d solved %d turns %d"
                      % (res["points"], res["levels"], res["solved"],
                         res["turns"]), flush=True)
    else:
        for trial in args.trials:
            for profile in args.profiles:
                print("trial %d profile %-11s ... " % (trial, profile),
                      end="", flush=True)
                res = run_one(kit_dir, repo_dir, trial, profile)
                results.append(res)
                if res["error"]:
                    print("ERROR %s" % res["error"], flush=True)
                else:
                    print("points %5d levels %d solved %d turns %d"
                          % (res["points"], res["levels"], res["solved"],
                             res["turns"]), flush=True)
    out_path = args.out or os.path.join(repo_dir, "tests",
                                        "mock_results.json")
    with open(out_path, "w") as fh:
        json.dump(results, fh, indent=2)
    print("\n%-11s %6s %6s %6s %6s" % ("profile", "mean", "min", "max",
                                       "solved"))
    for profile in args.profiles:
        pts = [r["points"] for r in results
               if r["profile"] == profile and r["points"] is not None]
        if not pts:
            print("%-11s   no scored runs" % profile)
            continue
        solved = sum(1 for r in results
                     if r["profile"] == profile and r["solved"])
        print("%-11s %6d %6d %6d %6d/%d  %s baseline %d"
              % (profile, sum(pts) // len(pts), min(pts), max(pts),
                 solved, len(pts),
                 "above" if sum(pts) // len(pts) > BASELINE else "BELOW",
                 BASELINE))
    print("\nwrote %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
