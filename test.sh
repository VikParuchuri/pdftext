#!/bin/bash

FILE_NAME="deepseek_1"
# Default values
INPUT_FILE="./input/${FILE_NAME}.pdf"
OUTPUT_JSON="./output/${FILE_NAME}_bbox.json"
VIZ_DIR="./output/${FILE_NAME}"
LOG_FILE="./output/${FILE_NAME}.log"
VISUALIZE="--visualize"

# Help function
show_help() {
  echo "Usage: ./run.sh [options]"
  echo "Options:"
  echo "  -i, --input FILE       Input PDF file (default: $INPUT_FILE)"
  echo "  -o, --output FILE      Output JSON file (default: $OUTPUT_JSON)"
  echo "  -v, --viz-dir DIR      Visualization output directory (default: $VIZ_DIR)"
  echo "  -n, --no-visualize     Disable visualization"
  echo "  -h, --help             Show this help message"
  exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -i|--input)
      INPUT_FILE="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_JSON="$2"
      shift 2
      ;;
    -v|--viz-dir)
      VIZ_DIR="$2"
      shift 2
      ;;
    -n|--no-visualize)
      VISUALIZE=""
      shift
      ;;
    -h|--help)
      show_help
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      ;;
  esac
done

# Run the parser with the specified or default options
python3 test.py "$INPUT_FILE" --json --out_path "$OUTPUT_JSON" --viz_output_dir "$VIZ_DIR" $VISUALIZE > "$LOG_FILE"
