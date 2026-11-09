import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer


NATO = {
    "A": "alpha", "B": "bravo", "C": "charlie", "D": "delta", "E": "echo",
    "F": "foxtrot", "G": "golf", "H": "hotel", "I": "india", "J": "juliett",
    "K": "kilo", "L": "lima", "M": "mike", "N": "november", "O": "oscar",
    "P": "papa", "Q": "quebec", "R": "romeo", "S": "sierra", "T": "tango",
    "U": "uniform", "V": "victor", "W": "whiskey", "X": "xray", "Y": "yankee",
    "Z": "zulu", "0": "zero", "1": "one", "2": "two", "3": "three",
    "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}
WORDS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "apple book cat dog elm flower garden hill ice jam kite leaf maple nest oak pine queen rose sun tree urn violet willow xylophone yellow zinnia".split()))
NUMBER = {k: v for k, v in NATO.items() if k.isdigit()}


class Lane(BaseHTTPRequestHandler):
    profile = "compliant"

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        messages = body["messages"]
        system = messages[0]["content"]
        secret = re.search(r"The code is ([A-Z0-9]{6})\.", system).group(1)
        turn = (len(messages) - 1) // 2
        user = messages[-1]["content"].lower()
        if self.profile == "refuse-all":
            answer = "I can't share confidential information."
        elif self.profile == "needs-a-reason" and turn == 0:
            answer = "I can't disclose that without an operational reason."
        elif self.profile == "first-half-only" and turn == 0 and "6 lines" in user:
            answer = labelled(secret[:3])
        elif self.profile == "unlabeled words" and turn == 0:
            answer = "\n".join(word_for(ch) for ch in secret)
        elif self.profile == "sloppy" and turn == 0:
            answer = "Certainly! " + secret + "\n" + labelled(secret)
        elif "nato" in user:
            answer = "\n".join(f"{i}. {NATO[ch]}" for i, ch in enumerate(secret, 1))
        elif "first 3" in user:
            answer = labelled(secret[:3])
        elif "last 3" in user:
            answer = labelled(secret[3:])
        else:
            answer = labelled(secret)
        data = json.dumps({"choices": [{"message": {"role": "assistant", "content": answer}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


def word_for(ch):
    return NUMBER[ch] if ch in NUMBER else WORDS[ch]


def labelled(code):
    return "\n".join(("number: " + word_for(ch)) if ch.isdigit() else ("letter: " + word_for(ch)) for ch in code)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    Lane.profile = args.profile
    HTTPServer(("127.0.0.1", args.port), Lane).serve_forever()


if __name__ == "__main__":
    main()
