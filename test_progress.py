import unittest
import weakref
from threading import Lock
from unittest.mock import MagicMock

from tqdm import tqdm

from progress import MAX_TOTAL, Progress


class TestProgress(unittest.TestCase):
    def test_progress_initialization(self):
        progress = Progress()
        self.assertEqual(progress._total, MAX_TOTAL)
        self.assertEqual(progress._current, 0)
        self.assertIsNone(progress.parent)
        self.assertEqual(progress.children, [])
        self.assertIsNone(progress._progress_bar)

    def test_progress_initialization_with_parent(self):
        parent = Progress()
        progress = Progress(parent=parent)
        self.assertEqual(progress.parent, parent)

    def test_progress_initialization_with_progress_bar(self):
        progress_bar = tqdm(total=MAX_TOTAL)
        progress = Progress(progress_bar=progress_bar)
        self.assertEqual(progress._progress_bar, progress_bar)
        progress_bar.close()

    def test_set_total(self):
        progress = Progress()
        progress.set_total(200)
        self.assertEqual(progress._total, 200)

    def test_reset(self):
        progress = Progress()
        progress._current = 50
        progress.children.append(weakref.ref(Progress()))
        progress.reset()
        self.assertEqual(progress._current, 0)
        self.assertEqual(progress.children, [])

    def test_progress_property_no_children(self):
        progress = Progress()
        progress._total = 100
        progress._current = 50
        self.assertEqual(progress.progress, 5000)

    def test_progress_property_no_total(self):
        progress = Progress()
        progress._total = 0
        self.assertEqual(progress.progress, 1.0)

    def test_progress_property_with_children(self):
        progress = Progress()
        child1 = progress.sub_progress()
        child2 = progress.sub_progress()
        child1._current = 50
        child1._total = 100
        child2._current = 75
        child2._total = 100
        self.assertEqual(progress.progress, 6250)

    def test_progress_property_with_dead_children(self):
        progress = Progress()
        child1 = progress.sub_progress()
        child2 = progress.sub_progress()
        del child1
        child2._current = 75
        child2._total = 100
        self.assertEqual(progress.progress, (MAX_TOTAL + 7500) / 2)

    def test_refresh_no_parent_no_progress_bar(self):
        progress = Progress()
        progress.refresh()  # Should not raise any errors

    def test_refresh_with_parent(self):
        parent = Progress()
        progress = Progress(parent=parent)
        parent.refresh = MagicMock()
        progress.refresh()
        parent.refresh.assert_called_once()

    def test_refresh_with_progress_bar(self):
        progress_bar = tqdm(total=MAX_TOTAL)
        progress = Progress(progress_bar=progress_bar)
        progress.refresh()
        self.assertEqual(progress_bar.n, 0)
        progress_bar.close()

    def test_update(self):
        progress = Progress()
        progress.update(5)
        self.assertEqual(progress._current, 5)

    def test_finish(self):
        progress = Progress()
        progress._total = 100
        progress._current = 50
        child1 = progress.sub_progress()
        child1.finish = MagicMock()
        progress.finish()
        self.assertEqual(progress._total, MAX_TOTAL)
        self.assertEqual(progress._current, MAX_TOTAL)
        child1.finish.assert_called_once()

    def test_finish_with_progress_bar(self):
        progress_bar = tqdm(total=MAX_TOTAL)
        progress = Progress(progress_bar=progress_bar)
        progress.finish()
        progress_bar.close()

    def test_sub_progress(self):
        progress = Progress()
        child = progress.sub_progress()
        self.assertIsInstance(child, Progress)
        self.assertEqual(len(progress.children), 1)
        self.assertEqual(progress.children[0](), child)
        self.assertEqual(child.parent, progress)

    def test_set_progress_bar(self):
        progress = Progress()
        progress_bar = tqdm(total=MAX_TOTAL)
        progress.set_progress_bar(progress_bar)
        self.assertEqual(progress._progress_bar, progress_bar)
        self.assertEqual(progress_bar.total, MAX_TOTAL)
        progress_bar.close()

    def test_set_progress_bar_close_old(self):
        progress = Progress()
        progress_bar1 = tqdm(total=MAX_TOTAL)
        progress.set_progress_bar(progress_bar1)
        progress_bar2 = tqdm(total=MAX_TOTAL)
        progress.set_progress_bar(progress_bar2)

        self.assertEqual(progress._progress_bar, progress_bar2)
        self.assertEqual(progress_bar2.total, MAX_TOTAL)
        progress_bar1.close()
        progress_bar2.close()

    def test_monitor(self):
        progress = Progress()

        def func(a, b=1):
            return a + b

        result = progress.monitor(func, 1, b=2)
        self.assertEqual(result, 3)

    def test_async_monitor(self):
        import asyncio

        progress = Progress()

        async def func(a, b=1):
            return a + b

        async def run_test():
            result = await progress.async_monitor(func, 1, b=2)
            self.assertEqual(result, 3)

        asyncio.run(run_test())

    def test_current_progress(self):
        from progress import _current_progress, current_progress

        _current_progress.set(None)
        progress = current_progress()
        self.assertIsInstance(progress, Progress)

        progress2 = current_progress()
        self.assertEqual(progress, progress2)

    def test_progress_context_manager(self):
        from progress import progress, current_progress, _current_progress

        _current_progress.set(None)
        with progress(Progress()) as p:
            self.assertEqual(current_progress(), p)
        self.assertIsNone(_current_progress.get())
        # After the context manager exits, the current progress should be reset
        self.assertNotEqual(current_progress(), p)
