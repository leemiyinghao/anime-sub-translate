from typing import Iterable, Optional

from production_litellm import litellm
from subtitle_types import (
    Dialogue,
    Metadata,
    TermBank,
)

from .base_task import TaskRequest
from .dto import (
    MetadataDTO,
    SubtitleDTO,
    TermBankDTO,
)
from .term_bank_task import CollectTermBankTask, RefineTermBankTask
from .translate_task import TranslateTask

litellm.enable_json_schema_validation = True
litellm.enable_cache = True


async def translate_dialogues(
    original: Iterable[Dialogue],
    target_language: str,
    pretranslate: Optional[TermBank] = None,
    metadata: Optional[Metadata] = None,
) -> Iterable[Dialogue]:
    """
    Translates the given text to the target language using litellm.
    :param content: The content to translate.
    :param target_language: The target language for translation.
    :param pretranslate: Optional pre-translation important names.
    :return: The translated text.
    """
    _subtitle = SubtitleDTO.from_subtitle(original)
    _term_bank = TermBankDTO.from_term_bank(pretranslate) if pretranslate else None
    _metadata = MetadataDTO.from_metadata(metadata) if metadata else None
    delta = await TaskRequest(
        TranslateTask(
            dialogues=_subtitle,
            target_language=target_language,
            term_bank=_term_bank,
            metadata=_metadata,
        )
    ).send()
    _subtitle = _subtitle.apply_delta(delta)
    return _subtitle.to_subtitle()


async def translate_context(
    original: Iterable[Dialogue],
    target_language: str,
    metadata: Optional[Metadata] = None,
    limit: Optional[int] = None,
) -> TermBank:
    """
    Extracts frequently used entities and their translations from the original text.
    :param original: The original text.
    :return: A list of important names and their translations.
    """
    _subtitle = SubtitleDTO.from_subtitle(original)
    _metadata = MetadataDTO.from_metadata(metadata) if metadata else None
    term_bank = await TaskRequest(
        CollectTermBankTask(
            dialogues=_subtitle,
            metadata=_metadata,
            target_language=target_language,
            char_limit=limit,
        )
    ).send()
    return term_bank.to_term_bank()


async def refine_context(
    target_language: str,
    contexts: TermBank,
    metadata: Optional[Metadata] = None,
    limit: Optional[int] = None,
) -> TermBank:
    """
    Refine the context before dialogue translation.
    :param target_language: The target language for translation.
    :param contexts: The original context.
    :param metadata: The metadata for the media set.
    :return: The refined context.
    """
    _term_bank = TermBankDTO.from_term_bank(contexts)
    _metadata = MetadataDTO.from_metadata(metadata) if metadata else None
    context_set = await TaskRequest(
        RefineTermBankTask(
            term_bank=_term_bank,
            metadata=_metadata,
            target_language=target_language,
            char_limit=limit,
        )
    ).send()
    return context_set.to_term_bank()
