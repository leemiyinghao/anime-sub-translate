import logging, argparse
from cost import CostTracker
from translate import translate
from setting import load_setting_with_env_file

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Translate subtitles to a target language."
    )
    parser.add_argument(
        "target_language", type=str, help="Target language for translation."
    )
    parser.add_argument("path", type=str, help="Path to the subtitle files.")

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    load_setting_with_env_file(".env")

    translate(args.path, args.target_language)

    logger.info("Translation completed.")
    logger.info(f"Estimated cost: {CostTracker().get_cost():.5f} USD")
