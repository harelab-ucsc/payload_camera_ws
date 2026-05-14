#!/usr/bin/env python3
"""
docker/tests/test_save_queue.py

Tests for the producer-consumer save queue in stream_processor.SyncNode.

Uses object.__new__ to bypass __init__ and tests queue mechanics in
isolation — no ROS 2 runtime or hardware required.
"""

import queue
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from stream_processor.stream_processor import SyncNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Logger:
    """Captures log calls so tests can assert on messages."""
    def __init__(self):
        self.records = []

    def info(self, msg):  self.records.append(('info',  msg))
    def warn(self, msg):  self.records.append(('warn',  msg))
    def error(self, msg): self.records.append(('error', msg))

    def any_contains(self, substr):
        return any(substr in msg for _, msg in self.records)

    def info_messages(self):
        return [msg for lvl, msg in self.records if lvl == 'info']


def _make_node():
    """
    Minimal SyncNode with only the queue infrastructure initialised.
    Bypasses __init__ so no ROS 2 context is needed.
    """
    node = object.__new__(SyncNode)
    node.save_queue = queue.Queue()
    node._save_workers = []
    node._logger = _Logger()
    node.get_logger = lambda: node._logger
    node.post_process_and_save = MagicMock()
    return node


def _start_workers(node, n=8):
    for _ in range(n):
        t = threading.Thread(target=node._save_worker, daemon=True)
        t.start()
        node._save_workers.append(t)


def _stop_workers(node):
    for _ in node._save_workers:
        node.save_queue.put(None)
    node.save_queue.join()


# ---------------------------------------------------------------------------
# _save_worker tests
# ---------------------------------------------------------------------------

class TestSaveWorker(unittest.TestCase):

    def test_worker_calls_post_process_and_save(self):
        """Worker must call post_process_and_save for each queued item."""
        node = _make_node()
        _start_workers(node, n=1)

        data, stamp = {'cam0': 'img'}, MagicMock()
        node.save_queue.put((data, stamp))
        node.save_queue.join()
        _stop_workers(node)

        node.post_process_and_save.assert_called_once_with(data, stamp)

    def test_sentinel_stops_worker(self):
        """None sentinel must cause the worker thread to exit cleanly."""
        node = _make_node()
        t = threading.Thread(target=node._save_worker, daemon=True)
        t.start()
        node._save_workers.append(t)

        node.save_queue.put(None)
        t.join(timeout=2.0)

        self.assertFalse(t.is_alive(), "Worker should exit after sentinel")

    def test_eight_workers_run_concurrently(self):
        """8 items with slow saves should finish in ~1 slot, not 8 slots."""
        node = _make_node()
        _start_workers(node, n=8)

        barrier = threading.Barrier(8)

        def slow_save(data, stamp):
            barrier.wait(timeout=3.0)   # all 8 must arrive here simultaneously
            time.sleep(0.05)

        node.post_process_and_save.side_effect = slow_save

        for _ in range(8):
            node.save_queue.put(({'x': 1}, MagicMock()))

        start = time.monotonic()
        node.save_queue.join()
        elapsed = time.monotonic() - start

        _stop_workers(node)

        self.assertLess(elapsed, 0.4,
            f"8 workers took {elapsed:.2f}s — likely running serially, not concurrently")

    def test_multiple_items_all_processed(self):
        """Every item put on the queue must be processed exactly once."""
        node = _make_node()
        _start_workers(node, n=8)

        n_items = 20
        for i in range(n_items):
            node.save_queue.put(({'i': i}, MagicMock()))

        node.save_queue.join()
        _stop_workers(node)

        self.assertEqual(node.post_process_and_save.call_count, n_items)


# ---------------------------------------------------------------------------
# destroy_node drain tests
# ---------------------------------------------------------------------------

class TestShutdownDrain(unittest.TestCase):

    def _patched_destroy(self, node):
        """Call destroy_node with super().destroy_node() stubbed out."""
        with patch.object(SyncNode.__bases__[0], 'destroy_node', MagicMock()):
            node.destroy_node()

    def test_destroy_node_waits_for_all_saves(self):
        """destroy_node must not return until every queued save completes."""
        node = _make_node()
        _start_workers(node, n=8)

        saved = []

        def record_save(data, stamp):
            time.sleep(0.05)
            saved.append(data)

        node.post_process_and_save.side_effect = record_save

        n_items = 6
        for i in range(n_items):
            node.save_queue.put(({'i': i}, MagicMock()))

        self._patched_destroy(node)

        self.assertEqual(len(saved), n_items,
            f"Expected {n_items} saves before destroy returned, got {len(saved)}")

    def test_destroy_node_logs_pending_count(self):
        """destroy_node must log when there are items still in the queue."""
        node = _make_node()
        _start_workers(node, n=1)   # slow consumer — queue will back up

        def slow_save(data, stamp):
            time.sleep(0.15)

        node.post_process_and_save.side_effect = slow_save

        for _ in range(5):
            node.save_queue.put(({'x': 1}, MagicMock()))

        self._patched_destroy(node)

        self.assertTrue(
            node._logger.any_contains('save') or node._logger.any_contains('queue'),
            f"Expected shutdown log about pending saves. Got: {node._logger.records}"
        )

    def test_destroy_node_silent_when_queue_empty(self):
        """destroy_node must not emit queue-depth logs when already empty."""
        node = _make_node()
        _start_workers(node, n=8)

        self._patched_destroy(node)

        queue_msgs = [
            msg for lvl, msg in node._logger.records
            if 'queue' in msg.lower() or 'remaining' in msg.lower()
        ]
        self.assertEqual(len(queue_msgs), 0,
            f"Unexpected log messages when queue was empty: {queue_msgs}")


# ---------------------------------------------------------------------------
# _queue_watchdog tests
# ---------------------------------------------------------------------------

class TestQueueWatchdog(unittest.TestCase):

    def _run_watchdog_ticks(self, node, n_ticks):
        """Run the watchdog for exactly n_ticks then stop it."""
        ticks = [0]

        def fake_sleep(t):
            ticks[0] += 1
            if ticks[0] >= n_ticks:
                raise _StopWatchdog

        with patch('stream_processor.stream_processor.rclpy') as mock_rclpy, \
             patch('stream_processor.stream_processor.time') as mock_time:
            mock_rclpy.ok.return_value = True
            mock_time.sleep.side_effect = fake_sleep
            try:
                node._queue_watchdog()
            except _StopWatchdog:
                pass

    def test_watchdog_logs_when_queue_nonempty(self):
        """Watchdog must emit a log when the queue has pending items."""
        node = _make_node()
        node.save_queue.put(({'data': 'x'}, MagicMock()))

        self._run_watchdog_ticks(node, n_ticks=1)

        self.assertTrue(
            node._logger.any_contains('queue') or node._logger.any_contains('depth'),
            f"Expected queue-depth log. Got: {node._logger.records}"
        )

    def test_watchdog_silent_when_queue_empty(self):
        """Watchdog must not log anything when the queue is empty."""
        node = _make_node()

        self._run_watchdog_ticks(node, n_ticks=3)

        self.assertEqual(len(node._logger.info_messages()), 0,
            f"Watchdog should be silent when queue is empty. Got: {node._logger.records}")

    def test_watchdog_stops_when_rclpy_not_ok(self):
        """Watchdog loop must exit when rclpy.ok() returns False."""
        node = _make_node()
        ran = [False]

        def one_tick(t):
            ran[0] = True

        with patch('stream_processor.stream_processor.rclpy') as mock_rclpy, \
             patch('stream_processor.stream_processor.time') as mock_time:
            mock_rclpy.ok.side_effect = [True, False]
            mock_time.sleep.side_effect = one_tick

            node._queue_watchdog()  # should return on its own

        self.assertTrue(ran[0], "Watchdog should have run at least one tick")


class _StopWatchdog(Exception):
    pass


if __name__ == "__main__":
    unittest.main()
