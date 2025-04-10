from setting import load_setting_with_env_file

from .base import get_mediaset_metadata_by_id, search_mediaset_metadata

if __name__ == "__main__":
    load_setting_with_env_file(".env")
    metadata = search_mediaset_metadata("Joshi Luck!")
    if metadata:
        print(metadata.model_dump_json(indent=2))
    else:
        print("Media set not found.")

    metadata = get_mediaset_metadata_by_id(185660)
    if metadata:
        print(metadata.model_dump_json(indent=2))
    else:
        print("Media set not found.")
