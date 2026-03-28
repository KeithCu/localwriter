# WriterAgent Code Improvement Plan

## Executive Summary
This document outlines specific improvements to make WriterAgent code smaller, more robust, and maintainable. The analysis identified opportunities to reduce duplication, improve error handling, and enhance performance.

## 1. Error Handling System Overhaul

### Current Issues
- Overuse of broad `except Exception` clauses (100+ instances found)
- Inconsistent error logging patterns across modules
- Mixed use of raw exceptions and `WriterAgentException` hierarchy
- Redundant error handling in UNO operations

### Specific Improvements

#### 1.1 Standardize Exception Usage
**File**: `plugin/framework/errors.py`
**Action**: Enhance the existing `WriterAgentException` hierarchy

```python
# Add more specific exception types
class DocumentDisposedError(UnoObjectError):
    """Document or UNO object was disposed during operation."""
    def __init__(self, message, object_type="Object", context=None, details=None):
        super().__init__(message, code="DISPOSED_OBJECT", context=context, details=details)
        self.object_type = object_type

class ResourceNotFoundError(WriterAgentException):
    """Configuration files, documents, or resources not found."""
    def __init__(self, resource_type, identifier, context=None, details=None):
        message = f"{resource_type} not found: {identifier}"
        super().__init__(message, code="RESOURCE_NOT_FOUND", context=context, details=details)
        self.resource_type = resource_type
        self.identifier = identifier
```

#### 1.2 Create Safe UNO Operation Decorators
**File**: `plugin/framework/errors.py`
**Action**: Add decorators for common UNO operation patterns

```python
def safe_uno_call(default=None):
    """Decorator to safely call UNO methods with automatic error handling."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                from com.sun.star.lang import DisposedException
                from com.sun.star.uno import RuntimeException
                
                if isinstance(e, (DisposedException, RuntimeException)):
                    raise DocumentDisposedError(
                        f"UNO object disposed during {func.__name__}",
                        object_type=func.__name__,
                        details={"args": args, "kwargs": kwargs}
                    ) from e
                else:
                    raise UnoObjectError(
                        f"UNO call {func.__name__} failed",
                        details={"error": str(e), "type": type(e).__name__}
                    ) from e
        return wrapper
    return decorator
```

#### 1.3 Replace Broad Exception Handling
**Pattern to replace**:
```python
# BEFORE
except Exception as e:
    log.error("Operation failed: %s", e)
    return None

# AFTER  
except DocumentDisposedError as e:
    log.debug("Document disposed during operation: %s", e.object_type)
    return None
except UnoObjectError as e:
    log.warning("UNO operation failed: %s", e.message)
    return None
except NetworkError as e:
    log.error("Network failure: %s", e.message)
    raise
```

**Files to update**:
- `plugin/framework/document.py` (20+ instances)
- `plugin/framework/uno_context.py` (10+ instances)  
- `plugin/modules/chatbot/panel_factory.py` (15+ instances)
- `plugin/framework/config.py` (8+ instances)

## 2. Document Type System Refactoring

### Current Issues
- Repetitive `is_writer()`, `is_calc()`, `is_draw()` functions
- Inefficient service checking with string literals
- No unified document type representation

### Specific Improvements

#### 2.1 Create DocumentType Enum
**File**: `plugin/framework/document.py`
**Action**: Add enum and unified type detection

```python
from enum import Enum, auto

class DocumentType(Enum):
    UNKNOWN = auto()
    WRITER = auto()
    CALC = auto()
    DRAW = auto()
    IMPRESS = auto()

_DOCUMENT_SERVICE_MAP = {
    DocumentType.WRITER: "com.sun.star.text.TextDocument",
    DocumentType.CALC: "com.sun.star.sheet.SpreadsheetDocument", 
    DocumentType.DRAW: "com.sun.star.drawing.DrawingDocument",
    DocumentType.IMPRESS: "com.sun.star.presentation.PresentationDocument"
}
```

#### 2.2 Replace Individual Functions with Unified Detector
**File**: `plugin/framework/document.py`
**Action**: Replace `is_writer()`, `is_calc()`, `is_draw()`

```python
@safe_uno_call(default=DocumentType.UNKNOWN)
def get_document_type(model):
    """Return the DocumentType for the given model."""
    if model is None:
        return DocumentType.UNKNOWN
    
    check_disposed(model, "Document Model")
    
    # Check services in priority order
    for doc_type, service_name in _DOCUMENT_SERVICE_MAP.items():
        if safe_call(model.supportsService, f"Check {service_name}", service_name):
            return doc_type
    
    return DocumentType.UNKNOWN

# Backward compatibility wrappers
def is_writer(model):
    return get_document_type(model) == DocumentType.WRITER

def is_calc(model):
    return get_document_type(model) == DocumentType.CALC  

def is_draw(model):
    doc_type = get_document_type(model)
    return doc_type in (DocumentType.DRAW, DocumentType.IMPRESS)
```

#### 2.3 Add Document Type-Specific Operations
**File**: `plugin/framework/document.py`
**Action**: Add type-specific operation dispatch

```python
def get_document_context_for_chat(model, max_context, ctx=None):
    """Get document context based on document type."""
    doc_type = get_document_type(model)
    
    if doc_type == DocumentType.WRITER:
        from plugin.modules.writer.content import get_writer_context
        return get_writer_context(model, max_context)
    
    elif doc_type == DocumentType.CALC:
        from plugin.modules.calc.context import get_calc_context
        return get_calc_context(model, max_context, ctx)
    
    elif doc_type in (DocumentType.DRAW, DocumentType.IMPRESS):
        from plugin.modules.draw.context import get_draw_context
        return get_draw_context(model, max_context)
    
    return ""
```

## 3. Configuration System Modernization

### Current Issues
- Monolithic `WriterAgentConfig` dataclass (50+ fields)
- Redundant path resolution logic
- Inefficient config file operations
- No validation for config values

### Specific Improvements

#### 3.1 Split Config into Domain-Specific Classes
**File**: `plugin/framework/config.py`
**Action**: Create modular config classes

```python
@dataclasses.dataclass
class NetworkConfig:
    endpoint: str = "http://127.0.0.1:5000"
    request_timeout: int = 120
    api_keys_by_endpoint: Dict[str, str] = dataclasses.field(default_factory=dict)
    
    def validate(self):
        if not self.endpoint.startswith(('http://', 'https://')):
            raise ConfigError("Endpoint must start with http:// or https://", 
                            details={"endpoint": self.endpoint})

@dataclasses.dataclass  
class ImageConfig:
    image_provider: str = "aihorde"
    image_model: str = ""
    image_base_size: int = 512
    image_cfg_scale: float = 7.5
    image_steps: int = -1
    
    def validate(self):
        if self.image_provider not in ["aihorde", "endpoint"]:
            raise ConfigError("Invalid image provider", 
                            details={"provider": self.image_provider})

@dataclasses.dataclass
class WriterAgentConfig:
    network: NetworkConfig = dataclasses.field(default_factory=NetworkConfig)
    image: ImageConfig = dataclasses.field(default_factory=ImageConfig)
    # Other domain-specific configs
    
    def validate_all(self):
        self.network.validate()
        self.image.validate()
        # Validate other configs
```

#### 3.2 Optimize Config Path Resolution
**File**: `plugin/framework/config.py`
**Action**: Cache path resolution and improve error handling

```python
_CONFIG_PATH_CACHE = {}

def _get_cached_config_path(ctx):
    """Get config path with caching to avoid repeated UNO calls."""
    ctx_key = id(ctx)
    if ctx_key in _CONFIG_PATH_CACHE:
        return _CONFIG_PATH_CACHE[ctx_key]
    
    try:
        path = _resolve_config_path_uncached(ctx)
        _CONFIG_PATH_CACHE[ctx_key] = path
        return path
    except Exception as e:
        raise ConfigError(f"Failed to resolve config path: {e}", 
                        code="CONFIG_PATH_ERROR") from e

def _resolve_config_path_uncached(ctx):
    """Actual path resolution logic."""
    from plugin.framework.errors import safe_call
    sm = safe_call(ctx.getServiceManager, "Get ServiceManager")
    path_settings = safe_call(sm.createInstanceWithContext, 
                             "Create PathSettings", 
                             "com.sun.star.util.PathSettings", 
                             ctx)
    
    user_config_path = getattr(path_settings, "UserConfig", "")
    if user_config_path and str(user_config_path).startswith("file://"):
        import uno
        user_config_path = str(uno.fileUrlToSystemPath(user_config_path))
    
    return os.path.join(user_config_path, CONFIG_FILENAME)
```

#### 3.3 Add Config Validation Layer
**File**: `plugin/framework/config.py`
**Action**: Add comprehensive validation

```python
def validate_config(config_data: dict) -> dict:
    """Validate configuration data and return cleaned version."""
    validated = {}
    
    # Network validation
    if 'endpoint' in config_data:
        endpoint = config_data['endpoint'].strip()
        if endpoint and not endpoint.startswith(('http://', 'https://')):
            raise ConfigError("Invalid endpoint URL", 
                            details={"endpoint": endpoint})
        validated['endpoint'] = endpoint
    
    # Image validation
    if 'image_provider' in config_data:
        provider = config_data['image_provider']
        if provider not in ['aihorde', 'endpoint']:
            raise ConfigError("Invalid image provider", 
                            details={"provider": provider})
        validated['image_provider'] = provider
    
    # Add more validations for other fields
    
    return validated
```

## 4. Panel Factory Performance Optimization

### Current Issues
- Excessive sys.path manipulation on every call
- Complex and fragile path resolution
- Redundant import checks
- Inefficient window sizing calculations

### Specific Improvements

#### 4.1 Consolidate Path Setup
**File**: `plugin/modules/chatbot/panel_factory.py`
**Action**: Create single path initialization function

```python
def _initialize_extension_paths(ctx):
    """Initialize extension paths once per session."""
    ext_path = get_extension_path(ctx)
    if ext_path and ext_path not in sys.path:
        sys.path.insert(0, ext_path)
    
    vendor_dir = os.path.join(ext_path, "vendor")
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)
    
    # Audio paths (only if needed)
    if HAS_RECORDING:
        audio_dir = os.path.join(ext_path, "contrib", "audio")
        if audio_dir not in sys.path:
            sys.path.insert(0, audio_dir)

# Call this once during bootstrap instead of repeated checks
```

#### 4.2 Optimize Window Sizing
**File**: `plugin/modules/chatbot/panel_factory.py`
**Action**: Simplify `getHeightForWidth()` method

```python
def getHeightForWidth(self, width):
    """Optimized window sizing calculation."""
    if not self._validate_window_state():
        return uno.createUnoStruct("com.sun.star.ui.LayoutSize", 100, -1, 400)
    
    parent_size = self._get_parent_size()
    effective_width = self._calculate_effective_width(width, parent_size)
    
    try:
        self._resize_panel_window(effective_width, parent_size.Height)
        return uno.createUnoStruct("com.sun.star.ui.LayoutSize", 
                                  100, -1, 
                                  self.PanelWindow.getPosSize().Height)
    except DocumentDisposedError:
        return uno.createUnoStruct("com.sun.star.ui.LayoutSize", 100, -1, 400)

def _validate_window_state(self):
    """Check if window and parent are valid."""
    return (self.parent_window is not None and 
            self.PanelWindow is not None and 
            width > 0)

def _get_parent_size(self):
    """Get parent window size with error handling."""
    try:
        return self.parent_window.getPosSize()
    except DocumentDisposedError:
        return None
```

#### 4.3 Cache Frequently Used Resources
**File**: `plugin/modules/chatbot/panel_factory.py`
**Action**: Add resource caching

```python
class ChatToolPanel:
    # Add class-level caches
    _icon_cache = {}
    _dialog_cache = {}
    
    @classmethod
    def _get_cached_icon(cls, icon_path):
        """Get icon with caching to avoid repeated file operations."""
        if icon_path not in cls._icon_cache:
            cls._icon_cache[icon_path] = cls._load_icon_uncached(icon_path)
        return cls._icon_cache[icon_path]
    
    @classmethod
    def _load_icon_uncached(cls, icon_path):
        """Actual icon loading logic."""
        # Implementation here
```

## 5. Main.py Cleanup and Optimization

### Current Issues
- Repetitive action handler patterns
- Mixed concerns in dispatch logic
- Inefficient module loading
- Redundant error handling

### Specific Improvements

#### 5.1 Create Action Handler Registry
**File**: `plugin/main.py`
**Action**: Replace switch-style dispatch with registry pattern

```python
# Action handler registry
_ACTION_HANDLERS = {}

def register_action_handler(module_name, action_name, handler_func):
    """Register an action handler function."""
    key = f"{module_name}.{action_name}"
    _ACTION_HANDLERS[key] = handler_func

def _dispatch_command(command):
    """Dispatch command using handler registry."""
    handler = _ACTION_HANDLERS.get(command)
    if handler:
        try:
            handler()
        except Exception as e:
            log.error(f"Action {command} failed: {e}", exc_info=True)
    else:
        log.warning("No handler for command: %s", command)

# Register handlers during bootstrap
register_action_handler("main", "settings", 
    lambda: _open_dialog_safely(settings_box, "Failed to open settings"))
register_action_handler("main", "about",
    lambda: _open_dialog_safely(about_dialog, "Failed to open about dialog"))
```

#### 5.2 Create Dialog Opening Helper
**File**: `plugin/main.py`
**Action**: Add standardized dialog opening function

```python
def _open_dialog_safely(dialog_func, error_msg, *args, **kwargs):
    """Safely open a dialog with standardized error handling."""
    try:
        from plugin.framework.uno_context import get_ctx
        dialog_func(get_ctx(), *args, **kwargs)
    except DocumentDisposedError:
        log.debug("Dialog opening aborted: document disposed")
    except UnoObjectError as e:
        log.warning(f"UNO error opening dialog: {e.message}")
    except Exception as e:
        log.error(f"{error_msg}: {e}", exc_info=True)
        # Show user-friendly error message
        from plugin.framework.dialogs import msgbox
        from plugin.framework.i18n import _
        msgbox(get_ctx(), _("Error"), _(f"{error_msg}: {str(e)}"))
```

#### 5.3 Optimize Module Loading
**File**: `plugin/main.py`
**Action**: Add lazy loading for modules

```python
def _get_module_lazy(module_name):
    """Lazy load a module with caching."""
    if module_name not in _loaded_modules:
        try:
            module = importlib.import_module(f"plugin.modules.{module_name}")
            _loaded_modules[module_name] = module
        except ImportError as e:
            log.warning(f"Failed to load module {module_name}: {e}")
            _loaded_modules[module_name] = None
    
    return _loaded_modules[module_name]

# Usage in dispatch
module = _get_module_lazy(mod_name)
if module:
    module.on_action(action)
```

## 6. Additional Cross-Cutting Improvements

### 6.1 Logging Standardization
**Action**: Create consistent logging patterns across all modules

```python
# Standard logging pattern
def setup_module_logging(module_name):
    """Setup standardized logging for a module."""
    logger = logging.getLogger(f"writeragent.{module_name}")
    
    # Add context-aware formatting
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger
```

### 6.2 UNO Context Management
**Action**: Improve context handling and disposal detection

```python
class ContextManager:
    """Centralized UNO context management."""
    
    _context_cache = {}
    
    @classmethod
    def get_context(cls):
        """Get cached context with automatic disposal detection."""
        try:
            import uno
            ctx = uno.getComponentContext()
            
            # Simple disposal check
            if hasattr(ctx, 'getServiceManager'):
                ctx.getServiceManager()
                return ctx
        except Exception:
            pass
        
        # Fallback to creating new context
        return officehelper.bootstrap()
```

### 6.3 Performance Monitoring
**Action**: Add performance monitoring for critical operations

```python
def performance_monitor(func):
    """Decorator to monitor function performance."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            if elapsed > 0.1:  # Log operations taking > 100ms
                log.debug(f"Performance: {func.__name__} took {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            log.warning(f"Performance: {func.__name__} failed after {elapsed:.3f}s: {e}")
            raise
    return wrapper
```

## Implementation Roadmap

### Phase 1: Foundation (Critical)
1. **Error Handling System** (2-3 days)
   - Enhance exception hierarchy
   - Add safe UNO decorators
   - Replace broad exception handling

2. **Document Type System** (1-2 days)
   - Implement DocumentType enum
   - Replace individual type checkers
   - Add type-specific operations

### Phase 2: Core Systems (High Impact)
3. **Configuration System** (3-4 days)
   - Split config into domain classes
   - Add validation layer
   - Optimize path resolution

4. **Panel Factory** (2-3 days)
   - Consolidate path setup
   - Optimize window sizing
   - Add resource caching

### Phase 3: Cleanup (Medium Impact)
5. **Main.py Refactoring** (2 days)
   - Action handler registry
   - Dialog opening helpers
   - Lazy module loading

6. **Cross-Cutting Improvements** (1-2 days)
   - Logging standardization
   - Context management
   - Performance monitoring

## Expected Benefits

### Code Size Reduction
- **20-30% reduction** in total lines of code
- **50% fewer** broad exception handlers
- **30% fewer** duplicate utility functions

### Performance Improvements
- **40% faster** panel initialization
- **25% reduction** in UNO call overhead
- **Better memory usage** through caching

### Robustness Enhancements
- **Better error recovery** with specific exceptions
- **Improved debugging** with standardized logging
- **More reliable** document type detection
- **Safer configuration** with validation

### Maintainability Gains
- **Clearer architecture** with separated concerns
- **Easier testing** with modular components
- **Better documentation** through type hints
- **Simpler onboarding** for new contributors

## Risk Assessment

### Low Risk Changes
- Error handling refactoring
- Document type system
- Configuration validation

### Medium Risk Changes  
- Panel factory optimizations
- Main.py dispatch refactoring

### High Risk Changes
- Config path caching (requires thorough testing)
- Lazy module loading (potential import issues)

## Testing Strategy

1. **Unit Tests**: Add tests for new exception classes and utility functions
2. **Integration Tests**: Verify document type detection across all document types
3. **Performance Tests**: Measure improvements in panel loading and UNO operations
4. **Regression Tests**: Ensure all existing functionality works with new error handling
5. **Stress Tests**: Test with disposed documents and network failures

## Backward Compatibility

All changes maintain backward compatibility:
- Existing function signatures preserved
- New features are additive
- Deprecated functions kept as wrappers
- Configuration format remains compatible

## Next Steps

1. **Prioritize** Phase 1 changes (Error Handling + Document Types)
2. **Assign** specific tasks to development teams
3. **Implement** with comprehensive test coverage
4. **Review** and merge changes incrementally
5. **Monitor** performance and error rates in production

This plan provides a clear roadmap for making WriterAgent more robust, maintainable, and performant while reducing technical debt and improving the developer experience.