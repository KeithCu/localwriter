import threading
import queue
import pytest
from unittest.mock import patch, MagicMock

from plugin.framework.worker_pool import run_in_background

from plugin.framework.main_thread import (
    _WorkItem,
    execute_on_main_thread,
    post_to_main_thread,
    _work_queue,
    _get_async_callback,
    _make_callback_instance,
    _poke_vcl,
    _init_lock
)
from plugin.framework.main_thread import (
    _get_async_callback,
    _make_callback_instance,
    _poke_vcl,
    _init_lock
)
import plugin.framework.main_thread as mt

@pytest.fixture(autouse=True)
def empty_work_queue():
    while not _work_queue.empty():
        try:
            _work_queue.get_nowait()
        except queue.Empty:
            break

def test_work_item():
    def func(x): return x * 2
    item = _WorkItem(func, (5,), {})

    assert item.fn is func
    assert item.args == (5,)
    assert not item.event.is_set()

def test_execute_on_main_thread_direct():
    # Calling it from main thread should just execute synchronously
    def func():
        return 42

    # We are in the main thread of pytest
    assert threading.current_thread() is threading.main_thread()

    res = execute_on_main_thread(func)
    assert res == 42


@patch("plugin.framework.main_thread._get_async_callback")
@patch("plugin.framework.main_thread._poke_vcl")

def test_execute_on_main_thread_background(mock_poke, mock_get_async):
    """
    Test where caller is not threading.main_thread(), mock _get_async_callback
    to force AsyncCallback path, and validate results/exceptions are returned.
    """
    mock_get_async.return_value = MagicMock()

    def func_to_run(x):
        if x == 0:
            raise ValueError("Zero not allowed")
        return x * 10

    def mock_poke_vcl():
        # Simulate VCL event loop calling notify()
        try:
            item = _work_queue.get_nowait()
            try:
                item.result = item.fn(*item.args, **item.kwargs)
            except Exception as e:
                item.exception = e
            finally:
                item.event.set()
        except queue.Empty:
            pass

    mock_poke.side_effect = mock_poke_vcl

    results = {}
    exceptions = {}

    def bg_thread(val):
        try:
            res = execute_on_main_thread(func_to_run, val)
            results[val] = res
        except Exception as e:
            exceptions[val] = e

    t1 = run_in_background(bg_thread, 5, daemon=False)
    t2 = run_in_background(bg_thread, 0, daemon=False)

    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert results.get(5) == 50
    assert isinstance(exceptions.get(0), ValueError)
    assert str(exceptions[0]) == "Zero not allowed"


@patch("plugin.framework.main_thread._get_async_callback")
@patch("plugin.framework.main_thread._poke_vcl")

def test_execute_on_main_thread_timeout(mock_poke, mock_get_async):
    """
    Test that forces item.event.wait(timeout) to time out and asserts
    the raised TimeoutError message includes the function name.
    """
    mock_get_async.return_value = MagicMock()
    # mock_poke does nothing, so the work item is never executed

    def slow_func():
        pass

    exc_caught = None
    def bg_thread():
        nonlocal exc_caught
        try:
            execute_on_main_thread(slow_func, timeout=0.1)
        except Exception as e:
            exc_caught = e

    t = run_in_background(bg_thread, daemon=False)
    t.join(timeout=1.0)

    assert isinstance(exc_caught, TimeoutError)
    assert "slow_func" in str(exc_caught)
    assert "timed out after 0.1s" in str(exc_caught)


@patch("plugin.framework.main_thread._get_async_callback")
@patch("plugin.framework.main_thread._poke_vcl")

def test_post_to_main_thread_fire_and_forget(mock_poke, mock_get_async):
    """
    Test for post_to_main_thread() that ensures it enqueues the work item
    without blocking (and still calls _poke_vcl()).
    """
    mock_get_async.return_value = MagicMock()

    def my_func():
        pass

    post_to_main_thread(my_func)

    # Check that it enqueued the item
    item = _work_queue.get_nowait()
    assert item.fn is my_func

    # Check that it called _poke_vcl
    mock_poke.assert_called_once()

@pytest.fixture(autouse=True)
def reset_mt_globals():
    mt._initialized = False
    mt._async_callback_service = None
    mt._callback_instance = None
    with mt._init_lock:
        pass
    while not _work_queue.empty():
        try:
            _work_queue.get_nowait()
        except queue.Empty:
            break
    yield
    mt._initialized = False
    mt._async_callback_service = None
    mt._callback_instance = None

def test_get_async_callback_success(monkeypatch):
    import sys
    mock_uno = MagicMock()
    mock_ctx = MagicMock()
    mock_uno.getComponentContext.return_value = mock_ctx
    mock_smgr = MagicMock()
    mock_ctx.ServiceManager = mock_smgr
    mock_service = MagicMock()
    mock_smgr.createInstanceWithContext.return_value = mock_service

    monkeypatch.setitem(sys.modules, 'uno', mock_uno)

    with patch('plugin.framework.main_thread._make_callback_instance') as mock_make:
        mock_instance = MagicMock()
        mock_make.return_value = mock_instance
        res = mt._get_async_callback()

    assert res == mock_service
    assert mt._initialized == True
    assert mt._async_callback_service == mock_service
    assert mt._callback_instance == mock_instance

def test_get_async_callback_already_init():
    mt._initialized = True
    mock_svc = MagicMock()
    mt._async_callback_service = mock_svc
    assert mt._get_async_callback() == mock_svc

def test_get_async_callback_failure(monkeypatch):
    import sys
    mock_uno = MagicMock()
    mock_uno.getComponentContext.side_effect = Exception("No UNO")
    monkeypatch.setitem(sys.modules, 'uno', mock_uno)

    with patch('plugin.framework.main_thread.log.warning') as mock_warn:
        res = mt._get_async_callback()

    assert res is None
    assert mt._initialized == True
    assert mt._async_callback_service is None
    mock_warn.assert_called()

def test_get_async_callback_returns_none(monkeypatch):
    import sys
    mock_uno = MagicMock()
    mock_ctx = MagicMock()
    mock_uno.getComponentContext.return_value = mock_ctx
    mock_smgr = MagicMock()
    mock_ctx.ServiceManager = mock_smgr
    mock_smgr.createInstanceWithContext.return_value = None
    monkeypatch.setitem(sys.modules, 'uno', mock_uno)

    with patch('plugin.framework.main_thread.log.warning') as mock_warn:
        res = mt._get_async_callback()

    assert res is None
    assert mt._initialized == True
    mock_warn.assert_called()

def test_make_callback_instance():
    import sys
    mock_unohelper = MagicMock()
    class MockBase:
        pass
    mock_unohelper.Base = MockBase
    monkeypatch_modules = {
        'unohelper': mock_unohelper,
        'com': MagicMock(),
        'com.sun': MagicMock(),
        'com.sun.star': MagicMock(),
        'com.sun.star.awt': MagicMock()
    }

    with patch.dict(sys.modules, monkeypatch_modules):
        class MockXCallback:
            pass
        sys.modules['com.sun.star.awt'].XCallback = MockXCallback

        instance = mt._make_callback_instance()
        assert instance is not None
        assert hasattr(instance, 'notify')

def test_make_callback_instance_notify(monkeypatch):
    import sys
    mock_unohelper = MagicMock()
    class MockBase: pass
    mock_unohelper.Base = MockBase
    monkeypatch_modules = {
        'unohelper': mock_unohelper,
        'com': MagicMock(),
        'com.sun': MagicMock(),
        'com.sun.star': MagicMock(),
        'com.sun.star.awt': MagicMock()
    }

    with patch.dict(sys.modules, monkeypatch_modules):
        class MockXCallback: pass
        sys.modules['com.sun.star.awt'].XCallback = MockXCallback
        instance = mt._make_callback_instance()

        # Test empty queue
        instance.notify(None)

        # Test valid item
        def dummy_fn(x): return x * 2
        item = _WorkItem(dummy_fn, (10,), {})
        mt._work_queue.put(item)

        with patch('plugin.framework.main_thread._poke_vcl') as mock_poke:
            instance.notify(None)
            assert item.result == 20
            assert item.exception is None
            assert item.event.is_set()
            mock_poke.assert_not_called()

        # Test item that raises exception
        def dummy_fn_exc(): raise ValueError("test error")
        item2 = _WorkItem(dummy_fn_exc, (), {})
        mt._work_queue.put(item2)

        # Test queue not empty after popping
        item3 = _WorkItem(lambda: 1, (), {})
        mt._work_queue.put(item3)

        with patch('plugin.framework.main_thread._poke_vcl') as mock_poke:
            instance.notify(None)
            assert item2.result is None
            assert isinstance(item2.exception, ValueError)
            assert item2.event.is_set()
            mock_poke.assert_called_once()

        # Clear queue
        mt._work_queue.get_nowait()

def test_poke_vcl(monkeypatch):
    import sys
    mock_uno = MagicMock()
    mock_uno.Any.return_value = "AnyVal"
    monkeypatch.setitem(sys.modules, 'uno', mock_uno)

    mt._async_callback_service = MagicMock()
    mt._callback_instance = MagicMock()

    # Success case
    mt._poke_vcl()
    mt._async_callback_service.addCallback.assert_called_with(mt._callback_instance, "AnyVal")

    # Failure case 1: Any fails, retry without
    mt._async_callback_service.addCallback.side_effect = [Exception("error"), None]
    mt._poke_vcl()
    mt._async_callback_service.addCallback.assert_called_with(mt._callback_instance, None)

    # Failure case 2: Both fail
    mt._async_callback_service.addCallback.side_effect = Exception("error")
    with patch('plugin.framework.main_thread.log.warning') as mock_warn:
        mt._poke_vcl()
        mock_warn.assert_called_once()

    mt._async_callback_service = None
    mt._poke_vcl() # Should do nothing

def test_execute_on_main_thread_no_service():
    mt._async_callback_service = None
    mt._initialized = True # prevent initialization

    with patch('plugin.framework.main_thread._get_async_callback') as mock_get:
        mock_get.return_value = None

        # Test fallback path when not on main thread
        def bg_thread():
            return mt.execute_on_main_thread(lambda x: x*2, 5)

        t = threading.Thread(target=bg_thread)
        t.start()
        t.join()

        # In actual test, we can mock threading.current_thread
        with patch('threading.current_thread') as mock_thread, patch('threading.main_thread') as mock_main:
            mock_thread.return_value = "Thread-1"
            mock_main.return_value = "Thread-2"

            res = mt.execute_on_main_thread(lambda x: x*2, 5)
            assert res == 10

def test_post_to_main_thread_no_service():
    with patch('plugin.framework.main_thread._get_async_callback') as mock_get:
        mock_get.return_value = None

        # Test fallback
        called = False
        def fn(): nonlocal called; called = True

        mt.post_to_main_thread(fn)
        assert called

def test_execute_on_main_thread_success():
    with patch('threading.current_thread') as mock_thread, \
         patch('threading.main_thread') as mock_main, \
         patch('plugin.framework.main_thread._get_async_callback') as mock_get, \
         patch('plugin.framework.main_thread._poke_vcl') as mock_poke:

        mock_thread.return_value = "Thread-1"
        mock_main.return_value = "Thread-2"
        mock_get.return_value = MagicMock()

        def mock_vcl():
            item = mt._work_queue.get_nowait()
            item.result = item.fn(*item.args, **item.kwargs)
            item.event.set()

        mock_poke.side_effect = mock_vcl

        res = mt.execute_on_main_thread(lambda x: x*2, 5)
        assert res == 10

def test_get_async_callback_already_init_with_lock():
    mt._initialized = False
    mock_svc = MagicMock()

    # We want to test the case where _initialized becomes true while waiting for lock.
    # To do this, we can make the lock acquisition call a side effect that sets _initialized=True
    real_lock = mt._init_lock
    class FakeLock:
        def __enter__(self):
            mt._initialized = True
            mt._async_callback_service = mock_svc
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    mt._init_lock = FakeLock()
    try:
        assert mt._get_async_callback() == mock_svc
    finally:
        mt._init_lock = real_lock
