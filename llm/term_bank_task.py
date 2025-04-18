from typing import (
    Optional,
)

from .base_task import IBaseTask, NormalCharLimitTrait, ReasoningMessageTrait
from .dto import (
    MetadataDTO,
    SubtitleDTO,
    TermBankDTO,
)
from .utils import clear_indentation


class CollectTermBankTask(
    NormalCharLimitTrait,
    ReasoningMessageTrait,
    IBaseTask[TermBankDTO],
):
    """
    CollectContextTask is a subclass of BaseTask that represents a task for collecting context.
     It contains methods to handle the request and response DTOs.

    Note: Prompts are generated by Meta Prompting and fine-tuned by human.
    """

    _response_dto = TermBankDTO
    _dialogues: SubtitleDTO
    _metadata: Optional[MetadataDTO]
    _target_language: str
    _char_limit: int

    def __init__(
        self,
        dialogues: SubtitleDTO,
        metadata: Optional[MetadataDTO] = None,
        target_language: str = "English",
        char_limit: Optional[int] = None,
    ) -> None:
        """
        Initializes the CollectContextTask with the given dialogues.
        :param dialogues: The list of dialogues to collect context from.
        """
        self._dialogues = dialogues
        self._metadata = MetadataDTO.from_metadata(metadata) if metadata else None
        self._target_language = target_language
        self._char_limit = (
            char_limit or len(dialogues.model_dump_json(exclude_none=True)) // 10
        )

    def context_prompt(self) -> str:
        prompt = "Generate a Term Bank for a translation task using the following story as input:\n"
        prompt += clear_indentation(f"""
        Story:
        ```
        {self._dialogues.as_plain()}
        ```
        """)
        if self._metadata:
            prompt += f"Introduction:\n"
            prompt += "```" + "\n"
            prompt += self._metadata.to_plain() + "\n"
            prompt += "```"
            prompt += "\n"
            prompt += "\n"
        return prompt

    def action_prompt(self) -> str:
        return (
            clear_indentation("""
        Task Instructions:
        Reference introduction to understand the story as you need.
        Identify key terms that are critical for providing consistent translation (e.g., names, technical or context-specific terms, or uncommon expressions). Exclude common terms.
        Keep the number of key terms as less as possible.
        """)
            + "\n"
            + f"Prefill the translation for each key term in {self._target_language}.\n"
            + clear_indentation(
                """
        Add a brief description explaining the importance or contextual meaning of each key term.
        Provide the result in JSON format following this schema in the Final section. non-translated key term should be in the original language, and translated term should be in the target language.
        ```json
        {"context": {"${non-translated key term}": {"translated": "${translated term}", "description": "${description of term}"}}}
        ```
        Include your reasoning process in the Reason section to determine which key terms are needed before finalizing the JSON output.
"""
            )
            + "\n"
            + f"Response under {self._char_limit} characters.\n"
        )

    def sanity_check(self, response: TermBankDTO) -> bool:
        return True


class RefineTermBankTask(
    NormalCharLimitTrait,
    ReasoningMessageTrait,
    IBaseTask[TermBankDTO],
):
    """
    RefineTermBankTask is a subclass of BaseTask that represents a task for refining the term bank.
     It contains methods to handle the request and response DTOs.

    Note: Prompts are generated by Meta Prompting and fine-tuned by human.
    """

    _response_dto = TermBankDTO
    _term_bank: TermBankDTO
    _metadata: Optional[MetadataDTO]
    _target_language: str
    _char_limit: int

    def __init__(
        self,
        term_bank: TermBankDTO,
        metadata: Optional[MetadataDTO] = None,
        target_language: str = "English",
        char_limit: Optional[int] = None,
    ) -> None:
        """
        Initializes the RefineTermBankTask with the given dialogues.
        :param dialogues: The list of dialogues to refine the term bank from.
        """
        self._term_bank = term_bank
        self._metadata = MetadataDTO.from_metadata(metadata) if metadata else None
        self._target_language = target_language
        self._char_limit = (
            char_limit or len(term_bank.model_dump_json(exclude_none=True)) // 4
        )

    def context_prompt(self) -> str:
        prompt = clear_indentation(f"""
        Term Bank:
        ```json
        {self._term_bank.model_dump_json(exclude_none=True)}
        ```        
        """)

        if self._metadata:
            prompt += clear_indentation(f"""
        Introduction:
        ```
        {self._metadata.to_plain()}
        ```
        """)

        return prompt

    def action_prompt(self) -> str:
        return clear_indentation("""
        Generate an analysis of the provided translation term bank and introduction with the following steps:

        1. For each term in the term bank, provide a brief explanation of why that term is critical for ensuring a consistent translation of a long narrative text. Consider aspects such as character identity, cultural nuance, plot significance, and any unique attributes the term conveys.

        2. Based on your reasoning, determine which terms are indispensable (i.e. critical) for accurate translation. Only include terms that are essential for maintaining consistency in translation; omit any that are non-critical.

        3. Finally, output a JSON object with a single key "context". This key should map to an object where each key is the original term (non-translated key) and each value is an object containing the fields:
        - "translated": the term's translated string.
        - "description": the term's description.

        The JSON must be formatted exactly as follows:
        ```json
        {"context": {"${non-translated key term}": {"translated": "${translated term}", "description": "${description of term}"}}}
        ```

        Ensure that your final response includes both the reasoning for each selected term and the correctly formatted JSON output.
        """)

    def sanity_check(self, response: TermBankDTO) -> bool:
        return True
