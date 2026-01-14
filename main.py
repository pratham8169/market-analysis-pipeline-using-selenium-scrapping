"""
Market Sentiment Analysis Pipeline - Main Orchestrator

This script executes the full end-to-end pipeline:
1. Data Collection (Scraping X/Twitter)
2. Data Processing (Cleaning & Parquet Conversion)
3. Signal Analysis (Hybrid Sentiment & Visualization)

Usage:
    python main.py
"""

import sys
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))

try:
    from src import collection
    from src import processing
    from src import analysis
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import source modules. {e}")
    print("Ensure your folder structure looks like this:")
    print("  /market-sentiment")
    print("    /src")
    print("      collection.py")
    print("      processing.py")
    print("      analysis.py")
    print("    main.py")
    sys.exit(1)


def setup_root_logging():
    """Configures global logging for the orchestrator."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | MAIN     | %(message)s",
        datefmt="%H:%M:%S",
    )


def run_pipeline():
    """Runs the three stages of the pipeline in order."""

    setup_root_logging()
    logging.info("=" * 80)
    logging.info("🚀 STARTING MARKET SENTIMENT PIPELINE")
    logging.info("=" * 80)

    # --- STEP 1: DATA COLLECTION ---
    logging.info("\n>>> STEP 1: DATA COLLECTION (Scraping)")
    logging.info("Initializing Stealth Scraper...")
    try:
        # Note: This runs until the target is reached or user presses Ctrl+C
        collection.main()
    except KeyboardInterrupt:
        logging.warning("Scraping interrupted by user. Proceeding to processing...")
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        # We don't exit because we might still want to process existing data

    # --- STEP 2: DATA PROCESSING ---
    logging.info("\n>>> STEP 2: DATA PROCESSING (Cleaning & Storage)")
    try:
        processing.main()
    except Exception as e:
        logging.error(f"Processing failed: {e}")
        sys.exit(1)  # Critical failure if we can't process data

    # --- STEP 3: ANALYSIS & SIGNALS ---
    logging.info("\n>>> STEP 3: ANALYSIS (Signal Generation)")
    try:
        analysis.main()
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        sys.exit(1)

    logging.info("\n" + "=" * 80)
    logging.info("✅ PIPELINE COMPLETE")
    logging.info("   - Raw Data:      data/raw/")
    logging.info("   - Clean Data:    data/processed_parquet/")
    logging.info("   - Final Output:  data/signals/signals.png")
    logging.info("=" * 80)


if __name__ == "__main__":
    run_pipeline()
