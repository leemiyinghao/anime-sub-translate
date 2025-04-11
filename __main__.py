import argparse
import logging

from tqdm.contrib.logging import logging_redirect_tqdm

from cost import CostTracker
from logger import logger, set_log_level
from setting import get_setting, load_setting_with_env_file
from translate import translate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Translate subtitles to a target language."
    )
    parser.add_argument(
        "target_language", type=str, help="Target language for translation."
    )
    parser.add_argument("path", type=str, help="Path to the subtitle files.")

    args = parser.parse_args()

    load_setting_with_env_file(".env")

    set_log_level(get_setting().log_level)

    with logging_redirect_tqdm(loggers=[logger]):
        logger.info("Starting translation...")
        logger.info(f"Target language: {args.target_language}")
        logger.info(f"Subtitle path: {args.path}")
        logger.info(f"Using model: {get_setting().llm_model}")

        translate(args.path, args.target_language)

        logger.info("Translation completed.")
        logger.info(f"Estimated cost: {CostTracker().get_cost():.5f} USD")
