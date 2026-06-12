#This import looks redundant but is needed to run tests
import test_setup

import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

import discord

from src.records import QueueEntry
from src.help_queue import HelpQueue

"""This file conducts tests on the funcitonality of the Remove button using Mocks to simulate interactions with Discord's APi."""
# ==========================================================
# Helper functions
# ==========================================================

def make_entry(user_id: int, username: str = "", student_name: str = "",
               details: str = "", is_passoff: bool = False, in_person: bool = False):
    return QueueEntry(
        user_id=user_id,
        username=username or f"user_{user_id}",
        student_name=student_name,
        details=details,
        is_passoff=is_passoff,
        timestamp=datetime.now(),
        in_person=in_person,
    )


def make_mock_interaction(queue: HelpQueue, user_id: int = 999,
                          display_name: str = "TA_Test"):
    """Construct a mock Interaction with a client.queue."""
    mock = MagicMock(spec=discord.Interaction)
    mock.client = AsyncMock()
    mock.client.queue = queue
    mock.user = MagicMock()
    mock.user.id = user_id
    mock.user.display_name = display_name
    mock.response = MagicMock()
    mock.response.send_message = AsyncMock()
    mock.response.send_modal = AsyncMock()
    mock.response.defer = AsyncMock()
    mock.followup = MagicMock()
    mock.followup.send = AsyncMock()
    return mock



# ==========================================================
# HelpQueue Modification tests (Most important)
# ==========================================================

class TestHelpQueue(unittest.IsolatedAsyncioTestCase):

    async def test_remove_existing_user(self):
        q = HelpQueue()
        await q.add(make_entry(1))
        await q.add(make_entry(2))
        await q.remove(1)
        self.assertEqual(len(q.entries), 1)
        self.assertEqual(q.entries[0].user_id, 2)

    async def test_remove_nonexistent_user_does_nothing(self):
        q = HelpQueue()
        await q.add(make_entry(1))
        await q.remove(999)
        self.assertEqual(len(q.entries), 1)

    async def test_remove_from_empty_queue(self):
        q = HelpQueue()
        await q.remove(1)
        self.assertEqual(len(q.entries), 0)

    async def test_get_front_after_remove(self):
        q = HelpQueue()
        await q.add(make_entry(1))
        await q.add(make_entry(2))
        self.assertEqual((await q.get_front()).user_id, 1)
        await q.remove(1)
        self.assertEqual((await q.get_front()).user_id, 2)

    async def test_get_front_empty_queue(self):
        q = HelpQueue()
        self.assertIsNone(await q.get_front())


# ==========================================================
# RemoveStudentView construction
# ==========================================================

class TestRemoveStudentViewConstruction(unittest.IsolatedAsyncioTestCase):

    def test_options_include_cancel_first(self):
        from src.ui.views.ta_view import RemoveStudentView
        view = RemoveStudentView([make_entry(1, username="alice")])
        select = view.children[0]
        self.assertEqual(select.options[0].value, "__cancel__")
        self.assertEqual(select.options[0].label, "— Cancel —")

    def test_emoji_passoff_vs_question(self):
        from src.ui.views.ta_view import RemoveStudentView
        entries = [
            make_entry(1, username="a", is_passoff=True),
            make_entry(2, username="b", is_passoff=False),
        ]
        view = RemoveStudentView(entries)
        select = view.children[0]
        self.assertEqual(select.options[1].emoji.name, "✅")
        self.assertEqual(select.options[2].emoji.name, "❓")

    def test_label_prefers_student_name(self):
        from src.ui.views.ta_view import RemoveStudentView
        view = RemoveStudentView([make_entry(1, username="discord_abc", student_name="张三")])
        self.assertEqual(view.children[0].options[1].label, "张三")

    def test_label_falls_back_to_username(self):
        from src.ui.views.ta_view import RemoveStudentView
        view = RemoveStudentView([make_entry(1, username="discord_abc", student_name="")])
        self.assertEqual(view.children[0].options[1].label, "discord_abc")

    def test_label_truncated_at_100_chars(self):
        from src.ui.views.ta_view import RemoveStudentView
        view = RemoveStudentView([make_entry(1, username="x", student_name="A" * 150)])
        opt = view.children[0].options[1]
        self.assertLessEqual(len(opt.label), 100)
        self.assertTrue(opt.label.endswith("..."))

    def test_description_truncated(self):
        """description is at most 100 characters long (including the "#N " prefix)."""
        from src.ui.views.ta_view import RemoveStudentView
        view = RemoveStudentView([make_entry(1, username="x", details="D" * 200)])
        opt = view.children[0].options[1]
        self.assertLessEqual(len(opt.description), 100)

    def test_value_is_user_id_string(self):
        from src.ui.views.ta_view import RemoveStudentView
        view = RemoveStudentView([make_entry(123456, username="alice")])
        self.assertEqual(view.children[0].options[1].value, "123456")


# ==========================================================
# RemoveStudentView Callback
# ==========================================================

class TestRemoveStudentViewCallback(unittest.IsolatedAsyncioTestCase):

    async def test_cancel_option_defers_and_returns(self):
        """Select Cancel → defer and do not show the Modal."""
        from src.ui.views.ta_view import RemoveStudentView
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))

        interaction = make_mock_interaction(q)
        view = RemoveStudentView(q.entries)

        with patch.object(discord.ui.Select, 'values',
                          new_callable=PropertyMock) as mock_values:
            mock_values.return_value = ["__cancel__"]
            await view.select_callback(interaction)

        interaction.response.defer.assert_awaited_once()
        interaction.response.send_modal.assert_not_awaited()

    async def test_select_student_sends_modal(self):
        """Select a student → show RemoveConfirmModal with correct parameters."""
        from src.ui.views.ta_view import RemoveStudentView
        q = HelpQueue()
        await q.add(make_entry(1, username="alice", student_name="Alice"))

        interaction = make_mock_interaction(q)
        view = RemoveStudentView(q.entries)

        with patch.object(discord.ui.Select, 'values',
                          new_callable=PropertyMock) as mock_values:
            mock_values.return_value = ["1"]
            await view.select_callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args[0][0]
        self.assertEqual(modal.student_user_id, 1)
        self.assertEqual(modal.student_name, "Alice")

    async def test_student_already_removed_by_another_ta(self):
        """Concurrency: the selected student has already been removed by another TA."""
        from src.ui.views.ta_view import RemoveStudentView
        q = HelpQueue()
        # entry is not in the queue (simulate already removed)
        entry = make_entry(2, username="bob")

        interaction = make_mock_interaction(q)
        view = RemoveStudentView([entry])

        with patch.object(discord.ui.Select, 'values',
                          new_callable=PropertyMock) as mock_values:
            mock_values.return_value = ["2"]
            await view.select_callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        msg = interaction.response.send_message.call_args[0][0]
        self.assertIn("no longer in the queue", msg)


# ==========================================================
# RemoveConfirmModal functionality
# ==========================================================

class TestRemoveConfirmModal(unittest.IsolatedAsyncioTestCase):

    def test_init_stores_user_id_and_display_name(self):
        from src.ui.modals import RemoveConfirmModal
        modal = RemoveConfirmModal(123, "Alice")
        self.assertEqual(modal.student_user_id, 123)
        self.assertEqual(modal.student_name, "Alice")

    async def test_on_submit_removes_student(self):
        from src.ui.modals import RemoveConfirmModal
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))
        await q.add(make_entry(2, username="bob"))

        interaction = make_mock_interaction(q)
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.display_name = "alice"
        mock_user.send = AsyncMock()
        interaction.client.fetch_user = AsyncMock(return_value=mock_user)

        with patch("src.ui.modals.update_queue_messages", AsyncMock()), \
            patch("src.ui.modals.notify_next_if_changed", AsyncMock()):
            modal = RemoveConfirmModal(1, "Alice")
            await modal.on_submit(interaction)

        self.assertEqual(len(q.entries), 1)
        self.assertEqual(q.entries[0].user_id, 2)

    async def test_on_submit_notifies_new_front(self):
        """Removing the front of the queue calls notify_next_if_changed to notify the new front."""
        from src.ui.modals import RemoveConfirmModal
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))
        await q.add(make_entry(2, username="bob"))

        interaction = make_mock_interaction(q)
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.display_name = "alice"
        mock_user.send = AsyncMock()
        interaction.client.fetch_user = AsyncMock(return_value=mock_user)

        with patch("src.ui.modals.update_queue_messages", AsyncMock()), \
            patch("src.ui.modals.notify_next_if_changed", AsyncMock()) as mock_notify:
            modal = RemoveConfirmModal(1, "Alice")
            await modal.on_submit(interaction)

        mock_notify.assert_awaited_once()
        # The second argument front_before is the previous front of the queue (alice, user_id=1).
        self.assertEqual(mock_notify.call_args[0][1].user_id, 1)

    async def test_on_submit_no_notify_when_removed_not_front(self):
        """Removing a non-front student still calls notify_next_if_changed, but the old front remains unchanged."""
        from src.ui.modals import RemoveConfirmModal
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))
        await q.add(make_entry(2, username="bob"))

        interaction = make_mock_interaction(q)
        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.display_name = "bob"
        mock_user.send = AsyncMock()
        interaction.client.fetch_user = AsyncMock(return_value=mock_user)

        with patch("src.ui.modals.update_queue_messages", AsyncMock()), \
            patch("src.ui.modals.notify_next_if_changed", AsyncMock()) as mock_notify:
            modal = RemoveConfirmModal(2, "Bob")
            await modal.on_submit(interaction)

        mock_notify.assert_awaited_once()
        # The old front is alice (user_id=1), which differs from the removed bob (user_id=2).
        # notify_next_if_changed will compare the front before and after and should not send a DM if it is still alice.
        self.assertEqual(mock_notify.call_args[0][1].user_id, 1)

    async def test_on_submit_dm_to_student(self):
        from src.ui.modals import RemoveConfirmModal
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))

        interaction = make_mock_interaction(q)
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.display_name = "alice"
        mock_user.send = AsyncMock()
        interaction.client.fetch_user = AsyncMock(return_value=mock_user)

        with patch("src.ui.modals.update_queue_messages", AsyncMock()), \
            patch("src.ui.modals.notify_next_if_changed", AsyncMock()):
            modal = RemoveConfirmModal(1, "Alice")
            await modal.on_submit(interaction)

        mock_user.send.assert_awaited_once()
        self.assertIn("removed from the CS240 help queue", mock_user.send.call_args[0][0])

    async def test_on_submit_dm_includes_reason(self):
        from src.ui.modals import RemoveConfirmModal
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))

        interaction = make_mock_interaction(q)
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.display_name = "alice"
        mock_user.send = AsyncMock()
        interaction.client.fetch_user = AsyncMock(return_value=mock_user)

        with patch("src.ui.modals.update_queue_messages", AsyncMock()), \
            patch("src.ui.modals.notify_next_if_changed", AsyncMock()):
            modal = RemoveConfirmModal(1, "Alice")
            modal.reason = MagicMock()
            modal.reason.value = "Asked too many questions"
            await modal.on_submit(interaction)

        dm_text = mock_user.send.call_args[0][0]
        self.assertIn("Reason:", dm_text)
        self.assertIn("Asked too many questions", dm_text)

    async def test_on_submit_success_message(self):
        from src.ui.modals import RemoveConfirmModal
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))

        interaction = make_mock_interaction(q)
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.display_name = "alice"
        mock_user.send = AsyncMock()
        interaction.client.fetch_user = AsyncMock(return_value=mock_user)
        interaction.response.send_message = AsyncMock()

        with patch("src.ui.modals.update_queue_messages", AsyncMock()), \
            patch("src.ui.modals.notify_next_if_changed", AsyncMock()):
            modal = RemoveConfirmModal(1, "Alice")
            await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        msg = interaction.response.send_message.call_args[0][0]
        self.assertIn("has been removed from the queue by", msg)


# ==========================================================
# TAView.remove_from_queue button
# ==========================================================

class TestTAViewRemoveButton(unittest.IsolatedAsyncioTestCase):

    async def test_empty_queue_shows_message(self):
        from src.ui.views.ta_view import TAView
        q = HelpQueue()
        interaction = make_mock_interaction(q)
        view = TAView()

        # Find the remove button anywhere in the view hierarchy and trigger it.
        to_visit = list(view.children)
        while to_visit:
            item = to_visit.pop(0)
            # If this item is a button-like object, it may have a custom_id
            if getattr(item, "custom_id", None) == "remove_from_queue":
                await item.callback(interaction)
                break
            # Otherwise, if it has children (e.g., a Container/ActionRow), search them
            children = getattr(item, "children", None)
            if children:
                to_visit.extend(children)

        interaction.response.send_message.assert_awaited_once()
        msg = interaction.response.send_message.call_args[0][0]
        self.assertEqual(msg, "Queue is empty.")

    async def test_nonempty_queue_shows_select_with_legend(self):
        from src.ui.views.ta_view import TAView, RemoveStudentView
        q = HelpQueue()
        await q.add(make_entry(1, username="alice"))

        interaction = make_mock_interaction(q)
        view = TAView()

        # Trigger the remove button wherever it exists inside the view
        to_visit = list(view.children)
        while to_visit:
            item = to_visit.pop(0)
            if getattr(item, "custom_id", None) == "remove_from_queue":
                await item.callback(interaction)
                break
            children = getattr(item, "children", None)
            if children:
                to_visit.extend(children)

        interaction.response.send_message.assert_awaited_once()
        sent_view = interaction.response.send_message.call_args[1]["view"]
        self.assertIsInstance(sent_view, RemoveStudentView)
        text = interaction.response.send_message.call_args[0][0]
        self.assertIn("✅", text)
        self.assertIn("❓", text)
        self.assertIn("Passoff", text)
        self.assertIn("Question", text)


if __name__ == "__main__":
    unittest.main()
