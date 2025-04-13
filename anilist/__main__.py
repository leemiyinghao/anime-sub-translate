import asyncio

from logger import set_log_level
from setting import load_setting_with_env_file

from .base import get_mediaset_metadata_by_id, search_mediaset_metadata


async def main():
    # Search for metadata by title
    metadata = await search_mediaset_metadata("Attack on Titan")
    if metadata:
        print(metadata.model_dump_json(indent=2))
    else:
        print("Media set not found.")

    # Get metadata by ID
    metadata = await get_mediaset_metadata_by_id(185660)
    if metadata:
        print(metadata.model_dump_json(indent=2))
    else:
        print("Media set not found.")


if __name__ == "__main__":
    # Load settings from the environment file
    load_setting_with_env_file(".env")
    set_log_level("debug")
    # Run the main function
    asyncio.run(main())
