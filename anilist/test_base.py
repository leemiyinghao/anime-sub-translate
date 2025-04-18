import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from subtitle_types import Metadata

from anilist.base import (
    GET_MEDIA_BY_ID_QUERY,
    AniListCharacterConnectionDTO,
    AniListCharacterNameDTO,
    AniListCharacterNodeDTO,
    AniListCharacterPageInfoDTO,
    AniListMetadataDTO,
    AniListMetadataMediaResponseDTO,
    AniListMetadataMediasResponseDTO,
    AniListMetadataPageResponseDTO,
    AniListTitleDTO,
    _load_all_characters,
    _query_mediaset_metadata,
    _search_mediaset_metadata,
    get_mediaset_metadata_by_id,
    search_mediaset_metadata,
)


class TestAniListBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Sample data for testing
        self.sample_title_data = {
            "romaji": "Shingeki no Kyojin",
            "native": "進撃の巨人",
            "english": "Attack on Titan",
        }

        self.sample_character_name_data = {
            "full": "Eren Yeager",
            "alternative": ["Eren Jaeger"],
            "native": "エレン・イェーガー",
        }

        self.sample_character_node_data = {
            "name": self.sample_character_name_data,
            "gender": "Male",
        }

        self.sample_page_info_data = {
            "hasNextPage": True,
        }

        self.sample_character_connection_data = {
            "pageInfo": self.sample_page_info_data,
            "nodes": [self.sample_character_node_data],
        }

        self.sample_metadata_data = {
            "id": 16498,
            "title": self.sample_title_data,
            "synonyms": ["AoT", "SnK"],
            "description": "Several hundred years ago, humans were nearly exterminated by giants.",
            "characters": self.sample_character_connection_data,
        }

    @patch(
        "anilist.base.best_match",
        side_effect=lambda title, list, *args, **kwargs: list[0],
    )
    async def test_search_mediaset_metadata(self, mock_best_match):
        """Test the _search_mediaset_metadata function with mocked responses."""
        # Create a mock response for the first page
        first_page_response = AniListMetadataPageResponseDTO(
            Page=AniListMetadataMediasResponseDTO(
                media=[
                    AniListMetadataDTO(
                        id=16498,
                        title=AniListTitleDTO(**self.sample_title_data),
                        synonyms=["AoT", "SnK"],
                        description="Several hundred years ago, humans were nearly exterminated by giants.",
                        characters=AniListCharacterConnectionDTO(
                            pageInfo=AniListCharacterPageInfoDTO(hasNextPage=True),
                            nodes=[
                                AniListCharacterNodeDTO(
                                    **self.sample_character_node_data
                                )
                            ],
                        ),
                    )
                ]
            )
        )

        # Create mock response for additional character pages
        additional_character = AniListCharacterNodeDTO(
            name=AniListCharacterNameDTO(
                full="Mikasa Ackerman",
                alternative=["Mikasa Ackermann"],
                native="ミカサ・アッカーマン",
            ),
            gender="Female",
        )

        # Set up the mocks
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
            patch("anilist.base._load_all_characters") as mock_load_characters,
        ):
            # Configure the mocks
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_query.return_value = first_page_response
            mock_load_characters.return_value = [additional_character]

            # Call the function
            result = await _search_mediaset_metadata("Attack on Titan")

            # Verify the function was called with correct parameters
            mock_get_client.assert_called_once()
            mock_query.assert_called_once()
            mock_load_characters.assert_called_once_with(media_id=16498)

            # Verify the result
            self.assertIsNotNone(result)
            self.assertIsInstance(result, Metadata)
            assert result  # make pyright happy
            self.assertEqual(result.title, "進撃の巨人")
            self.assertIn("Shingeki no Kyojin", result.title_alt)
            self.assertIn("Attack on Titan", result.title_alt)
            self.assertEqual(
                len(result.characters), 2
            )  # One from first page, one from additional pages

            # Check first character
            self.assertEqual(result.characters[0].name, "エレン・イェーガー")
            self.assertIn("Eren Yeager", result.characters[0].name_alt)
            self.assertEqual(result.characters[0].gender, "Male")

            # Check second character
            self.assertEqual(result.characters[1].name, "ミカサ・アッカーマン")
            self.assertIn("Mikasa Ackerman", result.characters[1].name_alt)
            self.assertEqual(result.characters[1].gender, "Female")

    async def test_search_mediaset_metadata_no_results(self):
        """Test the _search_mediaset_metadata function when no results are found."""
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
        ):
            # Configure the mocks to return None (no results)
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_query.return_value = None

            # Call the function
            result = await _search_mediaset_metadata("Non-existent anime")

            # Verify the function was called with correct parameters
            mock_get_client.assert_called_once()
            mock_query.assert_called_once()

            # Verify the result is None
            self.assertIsNone(result)

    async def test_search_mediaset_metadata_error_handling(self):
        """Test the error handling in _search_mediaset_metadata."""
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
        ):
            # Configure the mocks to raise an exception
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_query.side_effect = Exception("API error")

            # Call the function through the public wrapper to test error handling
            result = await search_mediaset_metadata("Attack on Titan")

            # Verify the function was called
            mock_get_client.assert_called_once()
            mock_query.assert_called_once()

            # Verify the result is None due to error handling
            self.assertIsNone(result)

    async def test_get_mediaset_metadata_by_id(self):
        """Test the _get_mediaset_metadata_by_id function with mocked responses."""
        # Create a mock response for the first page
        first_page_response = AniListMetadataMediaResponseDTO(
            Media=AniListMetadataDTO(
                id=16498,
                title=AniListTitleDTO(**self.sample_title_data),
                synonyms=["AoT", "SnK"],
                description="Several hundred years ago, humans were nearly exterminated by giants.",
                characters=AniListCharacterConnectionDTO(
                    pageInfo=AniListCharacterPageInfoDTO(hasNextPage=True),
                    nodes=[AniListCharacterNodeDTO(**self.sample_character_node_data)],
                ),
            )
        )

        # Create mock response for additional character pages
        additional_character = AniListCharacterNodeDTO(
            name=AniListCharacterNameDTO(
                full="Mikasa Ackerman",
                alternative=["Mikasa Ackermann"],
                native="ミカサ・アッカーマン",
            ),
            gender="Female",
        )

        # Set up the mocks
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
            patch("anilist.base._load_all_characters") as mock_load_characters,
        ):
            # Configure the mocks
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_query.return_value = first_page_response
            mock_load_characters.return_value = [additional_character]

            # Call the function
            result = await get_mediaset_metadata_by_id(16498)

            # Verify the function was called with correct parameters
            mock_get_client.assert_called_once()
            mock_query.assert_called_once()
            mock_load_characters.assert_called_once_with(media_id=16498)

            # Verify the result
            self.assertIsNotNone(result)
            self.assertIsInstance(result, Metadata)
            assert result  # make pyright happy
            self.assertEqual(result.title, "進撃の巨人")
            self.assertIn("Shingeki no Kyojin", result.title_alt)
            self.assertIn("Attack on Titan", result.title_alt)
            self.assertEqual(
                len(result.characters), 2
            )  # One from first page, one from additional pages

            # Check first character
            self.assertEqual(result.characters[0].name, "エレン・イェーガー")
            self.assertIn("Eren Yeager", result.characters[0].name_alt)
            self.assertEqual(result.characters[0].gender, "Male")

            # Check second character
            self.assertEqual(result.characters[1].name, "ミカサ・アッカーマン")
            self.assertIn("Mikasa Ackerman", result.characters[1].name_alt)
            self.assertEqual(result.characters[1].gender, "Female")

    async def test_get_mediaset_metadata_by_id_no_results(self):
        """Test the _get_mediaset_metadata_by_id function when no results are found."""
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
        ):
            # Configure the mocks to return None (no results)
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_query.return_value = None

            # Call the function
            result = await get_mediaset_metadata_by_id(999999)  # Non-existent ID

            # Verify the function was called with correct parameters
            mock_get_client.assert_called_once()
            mock_query.assert_called_once()

            # Verify the result is None
            self.assertIsNone(result)

    async def test_get_mediaset_metadata_by_id_error_handling(self):
        """Test the error handling in _get_mediaset_metadata_by_id."""
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
        ):
            # Configure the mocks to raise an exception
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_query.side_effect = Exception("API error")

            # Call the function through the public wrapper to test error handling
            result = await get_mediaset_metadata_by_id(16498)

            # Verify the function was called
            mock_get_client.assert_called_once()
            mock_query.assert_called_once()

            # Verify the result is None due to error handling
            self.assertIsNone(result)

    async def test_load_all_characters(self):
        """Test the _load_all_characters function with mocked responses."""

        # Create mock responses for multiple pages
        page1_character = AniListCharacterNodeDTO(
            name=AniListCharacterNameDTO(
                full="Mikasa Ackerman",
                alternative=["Mikasa Ackermann"],
                native="ミカサ・アッカーマン",
            ),
            gender="Female",
        )

        page2_character = AniListCharacterNodeDTO(
            name=AniListCharacterNameDTO(
                full="Armin Arlert",
                alternative=["Armin Arlelt"],
                native="アルミン・アルレルト",
            ),
            gender="Male",
        )

        # Set up the mocks
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
        ):
            # Configure the mock to return different responses for different pages
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            # Configure mock_query to return different responses based on the page number
            async def mock_query_side_effect(client, query, variables, expect):
                page = variables.get("charaPage", 0)

                if page == 2:
                    # First additional page (page 2)
                    return AniListMetadataMediaResponseDTO(
                        Media=AniListMetadataDTO(
                            id=16498,
                            characters=AniListCharacterConnectionDTO(
                                pageInfo=AniListCharacterPageInfoDTO(hasNextPage=True),
                                nodes=[page1_character],
                            ),
                        )
                    )
                elif page == 3:
                    # Second additional page (page 3)
                    return AniListMetadataMediaResponseDTO(
                        Media=AniListMetadataDTO(
                            id=16498,
                            characters=AniListCharacterConnectionDTO(
                                pageInfo=AniListCharacterPageInfoDTO(hasNextPage=False),
                                nodes=[page2_character],
                            ),
                        )
                    )
                else:
                    # Any other page (should not be called in this test)
                    return None

            mock_query.side_effect = mock_query_side_effect

            # Call the function
            result = await _load_all_characters(media_id=16498, start_from=1)

            # Verify the function was called with correct parameters
            mock_get_client.assert_called_once()

            # Verify mock_query was called twice (once for each page)
            self.assertEqual(mock_query.call_count, 2)

            # Check the first call arguments
            first_call_args = mock_query.call_args_list[0][1]
            self.assertEqual(first_call_args["variables"]["mediaId"], 16498)
            self.assertEqual(first_call_args["variables"]["charaPage"], 2)

            # Check the second call arguments
            second_call_args = mock_query.call_args_list[1][1]
            self.assertEqual(second_call_args["variables"]["mediaId"], 16498)
            self.assertEqual(second_call_args["variables"]["charaPage"], 3)

            # Verify the result
            self.assertEqual(len(result), 2)

            # make pyright happy
            assert result[0].name.alternative
            assert result[1].name.alternative

            # Check first character
            self.assertEqual(result[0].name.full, "Mikasa Ackerman")
            self.assertIn("Mikasa Ackermann", result[0].name.alternative)
            self.assertEqual(result[0].gender, "Female")

            # Check second character
            self.assertEqual(result[1].name.full, "Armin Arlert")
            self.assertIn("Armin Arlelt", result[1].name.alternative)
            self.assertEqual(result[1].gender, "Male")

    async def test_load_all_characters_empty_response(self):
        """Test the _load_all_characters function when no characters are found."""

        # Set up the mocks
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
        ):
            # Configure the mock to return empty response
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_query.return_value = None

            # Call the function
            result = await _load_all_characters(media_id=999999, start_from=1)

            # Verify the function was called with correct parameters
            mock_get_client.assert_called_once()
            mock_query.assert_called_once()

            # Verify the result is an empty list
            self.assertEqual(result, [])

    async def test_load_all_characters_max_pages(self):
        """Test the _load_all_characters function with maximum page limit."""

        # Create a character for each page
        character_template = AniListCharacterNodeDTO(
            name=AniListCharacterNameDTO(
                full="Character", alternative=["Alt"], native="キャラクター"
            ),
            gender="Unknown",
        )

        # Set up the mocks
        with (
            patch("anilist.base._get_client") as mock_get_client,
            patch("anilist.base._query_mediaset_metadata") as mock_query,
        ):
            # Configure the mock to always return a page with hasNextPage=True
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            async def mock_query_side_effect(client, query, variables, expect):
                # Always return a response with hasNextPage=True to test the max page limit
                return AniListMetadataMediaResponseDTO(
                    Media=AniListMetadataDTO(
                        id=16498,
                        characters=AniListCharacterConnectionDTO(
                            pageInfo=AniListCharacterPageInfoDTO(hasNextPage=True),
                            nodes=[character_template],
                        ),
                    )
                )

            mock_query.side_effect = mock_query_side_effect

            # Call the function
            result = await _load_all_characters(media_id=16498, start_from=1)

            # Verify the function was called with correct parameters
            mock_get_client.assert_called_once()

            # Should stop at 10 pages (starting from page 2 to page 9 = 8 calls)
            self.assertEqual(mock_query.call_count, 8)

            # Verify the result has 8 characters (one for each page)
            self.assertEqual(len(result), 8)

    async def test_query_mediaset_metadata(self):
        """Test the _query_mediaset_metadata function with mocked responses."""

        # Set up the mocks
        with patch("anilist.base.get_setting") as mock_get_setting:
            # Mock the setting to return a test token
            mock_setting = MagicMock()
            mock_setting.anilist_token = "test_token"
            mock_get_setting.return_value = mock_setting

            # Create a mock client
            mock_client = AsyncMock()

            # Configure the mock client to return a valid response
            mock_client.execute_async.return_value = {
                "Media": self.sample_metadata_data
            }

            # Call the function
            variables = {"mediaId": 16498}
            _result = await _query_mediaset_metadata(
                client=mock_client,
                query=GET_MEDIA_BY_ID_QUERY,
                variables=variables,
                expect=AniListMetadataMediaResponseDTO,
            )
            assert _result  # make pyright happy
            result = _result.Media

            # Verify the client was called with correct parameters
            mock_client.execute_async.assert_called_once()
            call_args = mock_client.execute_async.call_args[1]
            self.assertEqual(call_args["variable_values"], variables)

            # Verify the result
            self.assertIsNotNone(result)
            self.assertIsInstance(result, AniListMetadataDTO)
            # make pyright happy
            assert (
                result
                and result.title
                and result.description
                and result.characters
                and result.characters.nodes
            )
            self.assertEqual(result.id, 16498)
            self.assertEqual(result.title.romaji, "Shingeki no Kyojin")
            self.assertEqual(result.title.native, "進撃の巨人")
            self.assertEqual(result.title.english, "Attack on Titan")
            self.assertEqual(result.synonyms, ["AoT", "SnK"])
            self.assertTrue("exterminated by giants" in result.description)
            self.assertEqual(len(result.characters.nodes), 1)
            self.assertEqual(result.characters.nodes[0].name.full, "Eren Yeager")

    async def test_query_mediaset_metadata_empty_response(self):
        """Test the _query_mediaset_metadata function with an empty response."""

        # Set up the mocks
        with patch("anilist.base.get_setting") as mock_get_setting:
            # Mock the setting to return a test token
            mock_setting = MagicMock()
            mock_setting.anilist_token = "test_token"
            mock_get_setting.return_value = mock_setting

            # Create a mock client
            mock_client = AsyncMock()

            # Configure the mock client to return an empty response
            mock_client.execute_async.return_value = {"Media": None}

            # Call the function
            variables = {"mediaId": 999999}  # Non-existent ID
            result = await _query_mediaset_metadata(
                client=mock_client,
                query=GET_MEDIA_BY_ID_QUERY,
                variables=variables,
                expect=AniListMetadataMediaResponseDTO,
            )
            assert result  # make pyright happy

            # Verify the client was called
            mock_client.execute_async.assert_called_once()

            # Verify the result is None
            self.assertIsNone(result.Media)

    async def test_query_mediaset_metadata_invalid_response(self):
        """Test the _query_mediaset_metadata function with an invalid response."""

        # Set up the mocks
        with patch("anilist.base.get_setting") as mock_get_setting:
            # Mock the setting to return a test token
            mock_setting = MagicMock()
            mock_setting.anilist_token = "test_token"
            mock_get_setting.return_value = mock_setting

            # Create a mock client
            mock_client = AsyncMock()

            # Configure the mock client to return an invalid response
            mock_client.execute_async.return_value = {
                "Media": {
                    "id": 16498,
                    # Missing other required fields
                }
            }

            # Call the function
            variables = {"mediaId": 16498}
            _result = await _query_mediaset_metadata(
                client=mock_client,
                query=GET_MEDIA_BY_ID_QUERY,
                variables=variables,
                expect=AniListMetadataMediaResponseDTO,
            )
            assert _result  # make pyright happy
            result = _result.Media

            # Verify the client was called
            mock_client.execute_async.assert_called_once()

            # Verify the result has default values for missing fields
            self.assertIsNotNone(result)
            assert result  # make pyright happy
            self.assertEqual(result.id, 16498)
            self.assertIsNone(result.title)
            self.assertIsNone(result.synonyms)
            self.assertIsNone(result.description)
            self.assertIsNone(result.characters)


if __name__ == "__main__":
    unittest.main()
