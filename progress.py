import weakref
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Awaitable, Callable, Generator, Optional, ParamSpec, TypeVar

from tqdm import tqdm

P = ParamSpec("P")
R = TypeVar("R")

MAX_TOTAL = 10000


class Progress:
    _current: int
    _total: int
    parent: Optional["Progress"] = None
    children: list[weakref.ReferenceType["Progress"]]
    _progress_bar: Optional["tqdm"] = None
    _lock: Lock

    def __init__(
        self,
        parent: Optional["Progress"] = None,
        progress_bar: Optional["tqdm"] = None,
    ):
        self._total = MAX_TOTAL
        self._current = 0
        self.parent: Optional["Progress"] = parent
        self.children = []
        if progress_bar:
            self.set_progress_bar(progress_bar)
        self._lock = Lock()

    def set_total(self, total: int):
        self._total = total
        self.refresh()

    def reset(self):
        self._current = 0
        self.children.clear()
        self.refresh()

    @property
    def progress(self) -> float:
        """
        Get the current progress, from 0 to 10000.
        :return: The current progress.
        """
        if self.children:
            progress = 0.0
            for child in self.children:
                if c := child():
                    progress += c.progress
                else:
                    progress += MAX_TOTAL
            return progress / len(self.children)
        if self._total == 0:
            return 1.0
        return self._current / self._total * MAX_TOTAL

    def refresh(self):
        if self.parent:
            self.parent.refresh()
        if self._progress_bar:
            self._progress_bar.n = int(self.progress)
            self._progress_bar.refresh()

    def update(self, n: int = 1):
        with self._lock:
            self._current += n
            self.refresh()

    def finish(self):
        if self._progress_bar:
            self._progress_bar.close()
        for child in self.children:
            if c := child():
                c.finish()
        self._total = self._current = MAX_TOTAL
        self.refresh()

    def sub_progress(self) -> "Progress":
        child = Progress(parent=self)
        self.children.append(weakref.ref(child))
        self.refresh()
        return child

    def set_progress_bar(self, progress_bar: "tqdm"):
        """
        Set the progress bar for this progress instance.
        :param progress_bar: The tqdm progress bar to set.
        """
        if self._progress_bar:
            self._progress_bar.close()
        self._progress_bar = progress_bar
        self._progress_bar.total = MAX_TOTAL
        self.refresh()

    def monitor(
        self,
        func: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """
        Wrap a function with progress tracking.
        :param func: The function to wrap.
        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.
        :return: The result of the function.
        """
        with progress(self):
            result = func(*args, **kwargs)

        return result

    async def async_monitor(
        self,
        func: Callable[P, Awaitable[R]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """
        Wrap an async function with progress tracking.
        :param func: The async function to wrap.
        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.
        :return: The result of the function.
        """
        with progress(self):
            result = await func(*args, **kwargs)

        return result


_current_progress: ContextVar[Optional[Progress]] = ContextVar(
    "_current_progress",
    default=None,
)


@contextmanager
def progress(
    progress: Progress,
) -> Generator[Progress, None, None]:
    """
    Context manager for progress tracking.
    :param total: Total number of items to process.
    """
    token = _current_progress.set(progress)
    yield progress
    _current_progress.reset(token)


def current_progress() -> Progress:
    """
    Get the current progress instance.
    :return: The current progress instance or a new Progress instance.
    """
    prog = _current_progress.get()
    if prog is None:
        prog = Progress()
        _current_progress.set(prog)
    return prog
