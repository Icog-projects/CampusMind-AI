"""CampusMind AI - Run Evaluation Entrypoint Script.

Executes chunking and caching benchmark experiments and writes technical reports.

Responsibilities:
1. main(): Orchestrates evaluation execution across chunking and caching benchmark runs.
"""

import os
import sys
import logging
from evaluation.chunking_comparison import ChunkingEvaluator
from evaluation.cache_comparison import CacheEvaluator
from evaluation.report_generator import generate_evaluation_markdown

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evaluation")


def main():
    print("=" * 60)
    print("CampusMind AI - Comprehensive Evaluation Suite (SRS v1.3)")
    print("=" * 60)

    # Output directory
    output_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Run Chunking Comparison
    print("\n[1/2] Running Chunking Comparison Experiment (Section 12.2)...")
    chunking_evaluator = ChunkingEvaluator()
    chunking_results = chunking_evaluator.run_all(output_dir=output_dir)

    # 2. Run Cache Comparison
    print("\n[2/2] Running Redis Caching Comparison Experiment (Section 12.3)...")
    cache_evaluator = CacheEvaluator()
    cache_results = cache_evaluator.run_benchmark(output_dir=output_dir)

    # 3. Generate Markdown Report
    print("\n[3/3] Generating Technical Evaluation Markdown Report...")
    report_md = generate_evaluation_markdown(chunking_results, cache_results)

    report_path = os.path.join(output_dir, "EVALUATION_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    # Also save to docs/ directory for project visibility
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs"))
    if os.path.exists(docs_dir):
        doc_report_path = os.path.join(docs_dir, "EVALUATION_REPORT.md")
        with open(doc_report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"Report also saved to docs: {doc_report_path}")

    print(f"\nEvaluation Complete! Results written to: {report_path}")
    print("=" * 60)
    print(report_md)
    print("=" * 60)


if __name__ == "__main__":
    main()

