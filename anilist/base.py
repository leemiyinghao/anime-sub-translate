from typing import Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import DocumentNode
from pydantic import BaseModel, computed_field
from setting import get_setting
from subtitle_types import CharacterInfo, MediaSetMetadata


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

    def to_metadata(self) -> MediaSetMetadata:
        return MediaSetMetadata(
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


def _search_mediaset_metadata(title: str) -> Optional[MediaSetMetadata]:
    """
    Searches for media set metadata by title.
    :param title: The title of the media set.
    :return: The media set metadata if found, None otherwise.
    """
    client = _get_client()
    query = SEARCH_MEDIA_QUERY
    variables = _create_search_variable(title)

    # First page
    first_page_response = _query_mediaset_metadata(
        client=client,
        query=query,
        variables=variables,
    )

    if first_page_response is None:
        return None

    # ensure fields
    first_page_response.characters = first_page_response.safe_characters
    first_page_response.characters.nodes = (
        first_page_response.safe_characters.safe_nodes
    )

    # Load all characters for the media set
    other_characters = _load_all_characters(media_id=first_page_response.id)
    # Append the characters to the first page response
    first_page_response.characters.nodes.extend(other_characters)

    return first_page_response.to_metadata()


def search_mediaset_metadata(title: str) -> Optional[MediaSetMetadata]:
    try:
        return _search_mediaset_metadata(title)
    except Exception as e:
        print(f"Error searching media set metadata: {e}")
        return None


def _get_mediaset_metadata_by_id(id: int) -> Optional[MediaSetMetadata]:
    client = _get_client()
    query = GET_MEDIA_BY_ID_QUERY
    variables = _create_id_variable(id)

    first_page_response = _query_mediaset_metadata(
        client=client,
        query=query,
        variables=variables,
    )

    if first_page_response is None:
        return None

    # ensure fields
    first_page_response.characters = first_page_response.safe_characters
    first_page_response.characters.nodes = (
        first_page_response.safe_characters.safe_nodes
    )

    other_characters = _load_all_characters(media_id=first_page_response.id)
    first_page_response.characters.nodes.extend(other_characters)
    return first_page_response.to_metadata()


def get_mediaset_metadata_by_id(id: int) -> Optional[MediaSetMetadata]:
    try:
        return _get_mediaset_metadata_by_id(id)
    except Exception as e:
        print(f"Error getting media set metadata by ID: {e}")
        return None


def _load_all_characters(
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
        response = _query_mediaset_metadata(
            client=client,
            query=query,
            variables=_variables,
        )

        if response is None or len(response.safe_characters.safe_nodes) == 0:
            break

        # Append the characters to the first page response
        result.extend(response.safe_characters.safe_nodes)
        has_next_page = response.safe_characters.safe_pageInfo.hasNextPage
        current_page += 1

    return result


def _query_mediaset_metadata(
    client: Client,
    query: DocumentNode,
    variables: dict,
) -> Optional[AniListMetadataDTO]:
    """
    Queries the media set metadata using the GraphQL client.
    :param client: The GraphQL client.
    :param query: The GraphQL query.
    :param variables: The variables for the query.
    :return: The media set metadata.
    """
    response = client.execute(query, variable_values=variables)
    if not response["Media"]:
        return None
    return AniListMetadataDTO.model_validate(response["Media"])


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
  Media(search: $search) {
    """
    + MEDIA_FRAGMENT
    + """
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
