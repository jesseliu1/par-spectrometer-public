"""V1.0.3's single-instance / serial-port lock, taken exactly as main.py takes it (16_ 2.1, 2.2).

main.py (V1.0.3, lines 71-79) holds QSharedMemory("VSCO_PAR_PAR_Spectrometer_SingleInstance") for its whole life:
create(1); if that fails, attach() and detach() once (a segment left behind by a debugger stop) and create(1)
again; if that fails too, another instance holds the lock. That code sits inside main() and cannot be imported, and
changing main.py would change the V1.0.3 line, so the same steps are repeated here line for line: the same key, no
extra retry, no timeout, never removing someone else's segment. tests/acquisition/test_instance_lock.py parses
main.py and compares the key and the call sequence with this module, so a later change of V1.0.3's lock turns that
test red. The native name Qt derives from the key depends on the Qt version: the alpha runs on PySide6 / Qt 6 and
V1.0.3 on PyQt5 / Qt 5, and Qt 6 derives the same name for a plain key as Qt 5 did (QSharedMemory(key) uses
legacyNativeKey). Two separate processes, one per binding, refuse each other in both directions (macOS, 2026-10-19;
tests/acquisition/test_instance_lock.py runs V1.0.3's real main.py in a PyQt5 process against this PySide6 lock;
internal notes section 4). NOT VERIFIED ON WINDOWS YET.

The alpha holds the lock only while it has taken over acquisition (D-212 question 1), as a member of the host,
never as a local variable; it is released after coordinator.stop() has returned.
"""

from __future__ import annotations

from ..qt_compat import QSharedMemory

INSTANCE_LOCK_KEY = "VSCO_PAR_PAR_Spectrometer_SingleInstance"
"""The key in V1.0.3's main.py; never change it here alone."""
LOCK_SIZE = 1
"""main.py creates the segment with create(1)."""


class InstanceLock:
    def __init__(self, key: str = INSTANCE_LOCK_KEY) -> None:
        self.key = key
        self._memory: QSharedMemory | None = None

    @property
    def held(self) -> bool:
        return self._memory is not None

    def acquire(self) -> bool:
        """main.py's steps; True when this object now holds the lock."""
        if self._memory is not None:
            return True
        instance_lock = QSharedMemory(self.key)
        if not instance_lock.create(LOCK_SIZE):
            # 调试器强制停止时共享内存段可能残留。先附加并释放本进程的引用后重试；
            # 若仍无法创建，说明确有另一活动实例在持有该锁。
            if instance_lock.attach():
                instance_lock.detach()
            if not instance_lock.create(LOCK_SIZE):
                return False
        self._memory = instance_lock
        return True

    def release(self) -> None:
        """Detach and drop the segment (V1.0.3 releases it when its process ends)."""
        memory, self._memory = self._memory, None
        if memory is not None:
            memory.detach()
