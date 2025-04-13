import argparse

from tqdm.contrib.logging import logging_redirect_tqdm

from cost import CostTracker
from logger import logger, set_log_level
from setting import get_setting, load_setting_with_env_file
from translate import (
    default_tasks,
    task_prepare_context,
    task_prepare_metadata,
    task_translate_files,
    translate,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Translate subtitles to a target language."
    )
    parser.add_argument(
        "target_language", type=str, help="Target language for translation."
    )
    parser.add_argument("path", type=str, help="Path to the subtitle files.")
    parser.add_argument(
        "--context", action="store_true", help="Prepare context for translation."
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Prepare metadata for translation.",
    )
    parser.add_argument(
        "--translate",
        action="store_true",
        help="Translate the subtitles.",
    )

    args = parser.parse_args()
    load_setting_with_env_file(".env")
    set_log_level(get_setting().log_level)

    # arrange tasks
    tasks = default_tasks
    if args.context or args.metadata or args.translate:
        _tasks = []
        if args.metadata:
            _tasks.append(task_prepare_metadata)
        if args.context:
            _tasks.append(task_prepare_context)
        if args.translate:
            _tasks.append(task_translate_files)
        tasks = tuple(_tasks)

    with logging_redirect_tqdm(loggers=[logger]):
        logger.info("Starting translation...")
        logger.info(f"Target language: {args.target_language}")
        logger.info(f"Subtitle path: {args.path}")
        logger.info(f"Using model: {get_setting().llm_model}")

        translate(args.path, args.target_language, tasks)

        logger.info("Translation completed.")
        logger.info(f"Estimated cost: {CostTracker().get_cost():.5f} USD")
