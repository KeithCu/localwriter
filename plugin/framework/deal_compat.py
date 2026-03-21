import os

# Check if we are in a debug/dev build
# In release builds, `make release` strips the `plugin/tests/` directory.
_is_debug_build = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "tests"))

def _noop_factory(*args, **kwargs):
    """
    No-op for decorators that take arguments, e.g.,
    @deal.pre(lambda x: x > 0)
    @deal.raises(ValueError)
    """
    def decorator(func):
        return func
    return decorator

def _noop_direct(func=None, **kwargs):
    """
    No-op for decorators that take no arguments, e.g.,
    @deal.pure
    or can be called as
    @deal.pure()
    """
    if func is None:
        # It was called as @deal.pure()
        return lambda f: f
    # It was called as @deal.pure
    return func

if _is_debug_build:
    try:
        # Try to import from vendored first
        import plugin.contrib.deal as deal
        pre = deal.pre
        post = deal.post
        ensure = deal.ensure
        raises = deal.raises
        pure = deal.pure
        inv = deal.inv
        reason = deal.reason
        safe = deal.safe
        chain = deal.chain
        has = deal.has
        example = deal.example
        catch = deal.catch
    except ImportError:
        try:
            # Fallback to system-wide if not vendored
            import deal
            pre = deal.pre
            post = deal.post
            ensure = deal.ensure
            raises = deal.raises
            pure = deal.pure
            inv = deal.inv
            reason = deal.reason
            safe = deal.safe
            chain = deal.chain
            has = deal.has
            example = deal.example
            catch = deal.catch
        except ImportError:
            # Fallback if deal is entirely missing
            pre = _noop_factory
            post = _noop_factory
            ensure = _noop_factory
            raises = _noop_factory
            inv = _noop_factory
            reason = _noop_factory
            chain = _noop_factory
            has = _noop_factory
            example = _noop_factory
            catch = _noop_factory

            pure = _noop_direct
            safe = _noop_direct
else:
    pre = _noop_factory
    post = _noop_factory
    ensure = _noop_factory
    raises = _noop_factory
    inv = _noop_factory
    reason = _noop_factory
    chain = _noop_factory
    has = _noop_factory
    example = _noop_factory
    catch = _noop_factory

    pure = _noop_direct
    safe = _noop_direct
