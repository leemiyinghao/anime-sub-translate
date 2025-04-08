import litellm
import os
import time

RETRY_TIMES = 20

def translate(text: str, target_language: str, pretranslate: str = None) -> str:
    """
        Translates the given text to the target language using litellm.
        :param text: The text to translate.
        :param target_language: The target language for translation.
        :param pretranslate: Optional pre-translation important names.
        :return: The translated text.
    """

    for retry in range(RETRY_TIMES):
        try:
            # Get model from environment variable or use default
            model = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
            extra_prompt = os.environ.get("LLM_EXTRA_PROMPT", "")

            # Prepare system message with name translations if provided
            system_message = f"""You are a translator. Translate the text to {target_language}.

    Important instructions:
    1. Preserve all formatting, line breaks, and special characters exactly as they appear in the original text.
    2. Do not add or remove any formatting elements.
    3. Maintain consistent translation of terms, names, and phrases throughout the text.
    4. For subtitle files, maintain the timing and structure of the original subtitles.
    6. It's not necessary to keep the original text in the translation as long as the meaning is preserved.
    7. Do not include any extra formatted text or comments in the translation.
    {extra_prompt}"""

            # Add name translation guidance if provided
            if pretranslate and pretranslate.strip():
                system_message += f"""
    8. Use the following translations for names and terms consistently:
    {pretranslate}"""

            response = litellm.completion(
                n=1,
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": text}
                ],
                stream=True
            )
            chunks = []
            for part in response:
                token = part.choices[0].delta.content or ""
                print(token, end='', flush=True)
                chunks.append(token)
            print("\n", end='', flush=True)
            return ''.join(chunks)
        except Exception as e:
            print(f"Translation error: {e}")
            if retry < RETRY_TIMES - 1:
                after = min(2 ** retry, 60)  # Exponential backoff
                print(f"Retrying after {after} seconds...")
                time.sleep(after)
            else:
                raise

def translate_names(text: str, target_language: str) -> str:
    """
    Translates the important names in the text to the target language using litellm. Like the name of a person, place, or organization.
        :param text: The text to translate.
        :param target_language: The target language for translation.
        :return: The translated text. It will be lines of {NAME} -> {TRANSLATED_NAME} pairs.
    """
    try:
        # Get model from environment variable or use default
        model = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
        extra_prompt = os.environ.get("LLM_EXTRA_PROMPT", "")
        
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": f"""You are a name translator. Extract and translate important names from the text to {target_language}.
                
Important instructions:
1. Identify names of people, places, organizations, and other proper nouns.
2. Provide translations for these names if appropriate in the target language.
3. For names that should not be translated, indicate they should remain as is.
4. Format your response as one name per line with the format: {{ORIGINAL_NAME}} -> {{TRANSLATED_NAME}}
5. If a name should not be translated, use: {{ORIGINAL_NAME}} -> {{ORIGINAL_NAME}}
6. Only include actual names, not common nouns or other text.
{extra_prompt}"""},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Name translation error: {e}")
        raise
