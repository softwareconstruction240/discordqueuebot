import test_setup
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from src.data_access.students_dao import get_registered_name, set_registered_name

class TestStudentsDAO(unittest.IsolatedAsyncioTestCase):

    @patch("src.data_access.students_dao.db_manager")
    async def test_get_registered_name_found(self, mock_db_manager):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("Jane Doe",)
        
        cursor_cm = MagicMock()
        cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
        cursor_cm.__aexit__ = AsyncMock(return_value=None)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = cursor_cm
        
        conn_cm = MagicMock()
        conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        conn_cm.__aexit__ = AsyncMock(return_value=None)

        mock_db_manager.get_conn.return_value = conn_cm

        name = await get_registered_name(12345)
        self.assertEqual(name, "Jane Doe")
        mock_cursor.execute.assert_called_once_with(
            "SELECT registered_name FROM students WHERE discord_id = %s",
            (12345,)
        )

    @patch("src.data_access.students_dao.db_manager")
    async def test_get_registered_name_not_found(self, mock_db_manager):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None
        
        cursor_cm = MagicMock()
        cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
        cursor_cm.__aexit__ = AsyncMock(return_value=None)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = cursor_cm

        conn_cm = MagicMock()
        conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        conn_cm.__aexit__ = AsyncMock(return_value=None)

        mock_db_manager.get_conn.return_value = conn_cm

        name = await get_registered_name(99999)
        self.assertIsNone(name)

    @patch("src.data_access.students_dao.db_manager")
    async def test_set_registered_name(self, mock_db_manager):
        mock_cursor = AsyncMock()
        
        cursor_cm = MagicMock()
        cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
        cursor_cm.__aexit__ = AsyncMock(return_value=None)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = cursor_cm

        conn_cm = MagicMock()
        conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        conn_cm.__aexit__ = AsyncMock(return_value=None)

        mock_db_manager.get_conn.return_value = conn_cm

        await set_registered_name(12345, "John Doe")
        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        self.assertIn("INSERT INTO students", args[0])
        self.assertEqual(args[1], (12345, "John Doe"))


if __name__ == "__main__":
    unittest.main()
