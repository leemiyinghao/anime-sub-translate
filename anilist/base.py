from typing import List, Optional, Type, TypeVar

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import DocumentNode
from logger import logger
from pydantic import BaseModel, computed_field
from setting import get_setting
from subtitle_types import CharacterInfo, Metadata
from utils import best_match


class AniListTitleDTO(BaseModel):
    romaji: Optional[str] = None
    native: Optional[str] = None
    english: Optional[str] = None

    @computed_field
    @property
    def safe_native(self) -> str:
        return self.native or ""

    @computed_field
    @property
    def safe_english(self) -> str:
        return self.english or ""

    @computed_field
    @property
    def safe_romaji(self) -> str:
        return self.romaji or ""


class AniListCharacterNameDTO(BaseModel):
    full: Optional[str] = None
    alternative: Optional[list[str]] = None
    native: Optional[str] = None

    @computed_field
    @property
    def safe_full(self) -> str:
        return self.full or ""

    @computed_field
    @property
    def safe_alternative(self) -> list[str]:
        return self.alternative or []

    @computed_field
    @property
    def safe_native(self) -> str:
        return self.native or ""


class AniListCharacterNodeDTO(BaseModel):
    name: AniListCharacterNameDTO
    gender: Optional[str] = None

    @computed_field
    @property
    def safe_name(self) -> AniListCharacterNameDTO:
        return self.name or AniListCharacterNameDTO()

    @computed_field
    @property
    def safe_gender(self) -> str:
        return self.gender or ""


class AniListCharacterPageInfoDTO(BaseModel):
    hasNextPage: bool = False


class AniListCharacterConnectionDTO(BaseModel):
    pageInfo: Optional[AniListCharacterPageInfoDTO] = None
    nodes: Optional[list[AniListCharacterNodeDTO]] = None

    @computed_field
    @property
    def safe_pageInfo(self) -> AniListCharacterPageInfoDTO:
        return self.pageInfo or AniListCharacterPageInfoDTO()

    @computed_field
    @property
    def safe_nodes(self) -> list[AniListCharacterNodeDTO]:
        return self.nodes or []


class AniListMetadataDTO(BaseModel):
    id: int
    title: Optional[AniListTitleDTO] = None
    synonyms: Optional[list[str]] = None
    description: Optional[str] = None
    characters: Optional[AniListCharacterConnectionDTO] = None

    @computed_field
    @property
    def safe_title(self) -> AniListTitleDTO:
        return self.title or AniListTitleDTO()

    @computed_field
    @property
    def safe_synonyms(self) -> list[str]:
        return self.synonyms or []

    @computed_field
    @property
    def safe_description(self) -> str:
        return self.description or ""

    @computed_field
    @property
    def safe_characters(self) -> AniListCharacterConnectionDTO:
        return self.characters or AniListCharacterConnectionDTO()

    def to_metadata(self) -> Metadata:
        return Metadata(
            title=self.safe_title.safe_native,
            title_alt=[self.safe_title.safe_romaji, self.safe_title.safe_english],
            description=self.safe_description,
            characters=[
                CharacterInfo(
                    name=character.safe_name.safe_native,
                    name_alt=[
                        character.safe_name.safe_full,
                        *character.safe_name.safe_alternative,
                    ],
                    gender=character.safe_gender,
                )
                for character in self.safe_characters.safe_nodes
            ],
        )


class AniListMetadataMediaResponseDTO(BaseModel):
    Media: Optional[AniListMetadataDTO]


class AniListMetadataMediasResponseDTO(BaseModel):
    media: List[AniListMetadataDTO]


class AniListMetadataPageResponseDTO(BaseModel):
    Page: AniListMetadataMediasResponseDTO


def _get_transport() -> AIOHTTPTransport:
    """
    Returns the transport for the GraphQL client.
    """
    headers = {}
    if token := get_setting().anilist_token:
        headers["Authorization"] = f"Bearer {token}"
    return AIOHTTPTransport(
        url="https://graphql.anilist.co/",
        headers=headers,
        ssl=True,
    )


def _get_client() -> Client:
    """
    Returns the GraphQL client.
    """
    return Client(
        transport=_get_transport(),
        fetch_schema_from_transport=False,
    )


async def _search_mediaset_metadata(title: str) -> Optional[Metadata]:
    """
    Searches for media set metadata by title.
    :param title: The title of the media set.
    :return: The media set metadata if found, None otherwise.
    """
    client = _get_client()
    query = SEARCH_MEDIA_PAGE_QUERY
    variables = _create_search_variable(title)

    candidate_list_response = await _query_mediaset_metadata(
        client=client,
        query=query,
        variables=variables,
        expect=AniListMetadataPageResponseDTO,
    )
    candidate_list = None
    if not candidate_list_response or not (
        candidate_list := candidate_list_response.Page.media
    ):
        return None

    logger.debug(
        f"Found {len(candidate_list)} candidates for title '{title}' on AniList:"
    )
    for candidate in candidate_list:
        logger.debug(
            f" - {candidate.safe_title.safe_native} ({candidate.safe_title.safe_english},{candidate.safe_title.safe_romaji})"
        )

    # First page
    first_page_response = best_match(
        title,
        candidate_list,
        key=lambda x: [
            x.safe_title.safe_native,
            x.safe_title.safe_english,
            x.safe_title.safe_romaji,
        ],
        threshold=0.2,
    )
    if not first_page_response:
        return None

    # ensure fields
    first_page_response.characters = first_page_response.safe_characters
    first_page_response.characters.nodes = (
        first_page_response.safe_characters.safe_nodes
    )

    # Load all characters for the media set
    other_characters = await _load_all_characters(media_id=first_page_response.id)
    # Append the characters to the first page response
    first_page_response.characters.nodes.extend(other_characters)

    return first_page_response.to_metadata()


async def search_mediaset_metadata(title: str) -> Optional[Metadata]:
    try:
        return await _search_mediaset_metadata(title)
    except Exception as e:
        print(f"Error searching media set metadata: {e}")
        return None


async def _get_mediaset_metadata_by_id(id: int) -> Optional[Metadata]:
    client = _get_client()
    query = GET_MEDIA_BY_ID_QUERY
    variables = _create_id_variable(id)

    response = await _query_mediaset_metadata(
        client=client,
        query=query,
        variables=variables,
        expect=AniListMetadataMediaResponseDTO,
    )
    first_page_response = None
    if not response or not (first_page_response := response.Media):
        return None

    # ensure fields
    first_page_response.characters = first_page_response.safe_characters
    first_page_response.characters.nodes = (
        first_page_response.safe_characters.safe_nodes
    )

    other_characters = await _load_all_characters(media_id=first_page_response.id)
    first_page_response.characters.nodes.extend(other_characters)
    return first_page_response.to_metadata()


async def get_mediaset_metadata_by_id(id: int) -> Optional[Metadata]:
    try:
        return await _get_mediaset_metadata_by_id(id)
    except Exception as e:
        print(f"Error getting media set metadata by ID: {e}")
        return None


async def _load_all_characters(
    media_id: int, start_from: int = 1
) -> list[AniListCharacterNodeDTO]:
    """
    Loads all characters for the media set by ID.
    :param id: The ID of the media set.
    :return: A list of characters for the media set.
    """
    client = _get_client()
    query = CHARACTER_QUERY
    result: list[AniListCharacterNodeDTO] = []

    # fetch 10 pages at most
    current_page = start_from + 1
    has_next_page = True
    while has_next_page and current_page < 10:
        # Check if there are more pages of characters
        _variables = _create_id_variable(id=media_id, chara_page=current_page)
        response = await _query_mediaset_metadata(
            client=client,
            query=query,
            variables=_variables,
            expect=AniListMetadataMediaResponseDTO,
        )
        media_response = None
        if not response or not (media_response := response.Media):
            break

        if len(media_response.safe_characters.safe_nodes) == 0:
            break

        # Append the characters to the first page response
        result.extend(media_response.safe_characters.safe_nodes)
        has_next_page = media_response.safe_characters.safe_pageInfo.hasNextPage
        current_page += 1

    return result


T = TypeVar("T", bound=Type[BaseModel])


async def _query_mediaset_metadata(
    client: Client,
    query: DocumentNode,
    variables: dict,
    expect: T,
) -> Optional[T]:
    """
    Queries the media set metadata using the GraphQL client.
    :param client: The GraphQL client.
    :param query: The GraphQL query.
    :param variables: The variables for the query.
    :return: The media set metadata.
    """
    response = await client.execute_async(query, variable_values=variables)
    return expect.model_validate(response)


def _create_search_variable(
    title: str, chara_page: int = 0, chara_per_page: int = 20
) -> dict:
    """
    Queries the search variable for the media set metadata.
    :param client: The GraphQL client.
    :param title: The title of the media set.
    :param chara_page: The page number for characters.
    :param chara_per_page: The number of characters per page.
    :param id: The ID of the media set.
    :return: The search variable for the media set metadata.
    """
    variables = {
        "search": title,
        "charaPage": chara_page,
        "charaPerPage": chara_per_page,
    }
    return variables


def _create_id_variable(id: int, chara_page: int = 0, chara_per_page: int = 20) -> dict:
    """
    Queries the ID variable for the media set metadata.
    :param client: The GraphQL client.
    :param id: The ID of the media set.
    :param chara_page: The page number for characters.
    :param chara_per_page: The number of characters per page.
    :return: The ID variable for the media set metadata.
    """
    variables = {
        "mediaId": id,
        "charaPage": chara_page,
        "charaPerPage": chara_per_page,
    }
    return variables


CHARACTER_FRAGMENT = """
      nodes {
        gender
        name {
          full
          alternative
          native
        }
      }
      pageInfo {
        hasNextPage
      }
"""

MEDIA_FRAGMENT = (
    """
    id
    characters(page: $charaPage, perPage: $charaPerPage) {
"""
    + CHARACTER_FRAGMENT
    + """
    }
    title {
      romaji
      native
      english
    }
    synonyms
    type
    description
"""
)

GET_MEDIA_BY_ID_QUERY = gql(
    """query Media($mediaId: Int, $charaPage: Int, $charaPerPage: Int) {
  Media(id: $mediaId) {
    """
    + MEDIA_FRAGMENT
    + """
  }
}"""
)


SEARCH_MEDIA_QUERY = gql(
    """query Media($search: String, $charaPage: Int, $charaPerPage: Int) {
  Media(search: $search, type: ANIME) {
    """
    + MEDIA_FRAGMENT
    + """
  }
}"""
)

SEARCH_MEDIA_PAGE_QUERY = gql(
    """query Media($search: String, $charaPage: Int, $charaPerPage: Int) {
  Page (perPage: 5){
    media(search: $search, type: ANIME) {
      """
    + MEDIA_FRAGMENT
    + """
    }
  }
}"""
)

CHARACTER_QUERY = gql(
    """query Media($mediaId: Int, $charaPage: Int, $charaPerPage: Int) {
  Media(id: $mediaId) {
    id
    characters(page: $charaPage, perPage: $charaPerPage) {
    """
    + CHARACTER_FRAGMENT
    + """
    }
  }
}"""
)
