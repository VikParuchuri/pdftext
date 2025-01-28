import json
import argparse
from statistics import mean


def verify_scores(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    scores = data["alignments"]["pdftext"]
    mean_score = mean(scores)
    assert mean_score > 90, f"Scores do not meet the required threshold: {mean_score}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify benchmark scores")
    parser.add_argument("file_path", type=str, help="Path to the json file")
    args = parser.parse_args()
    verify_scores(args.file_path)
