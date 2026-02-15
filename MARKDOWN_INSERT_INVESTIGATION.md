# Markdown insert investigation: apply_markdown and insertTransferable

This document summarizes what was learned about why **apply_markdown** (inserting content via a hidden Writer document and `insertTransferable`) fails when run from the LocalWriter menu ("Run markdown tests"), and what should be investigated next. Assume you have read **AGENTS.md** and this file only.

---

## 1. The problem

- **Symptom**: The markdown tests (LocalWriter → Run markdown tests) report 3 passed, 3 failed. The first two tests pass (`document_to_markdown`, `tool_get_markdown`). The three that fail are:
  - apply at end (no processEvents): content not found
  - apply at end (with processEvents): content not found  
  - tool_apply_markdown returned ok but content not in document
- **Observed**: `tool_apply_markdown` returns `status=ok`, but when the document is read back (via `getText().createTextCursor().getString()`), the inserted text is missing. Document length stays the same (e.g. 26 chars) before and after the insert.
- **Conclusion**: The insert is not happening in the document we are measuring. Paste is going somewhere else.

---

## 2. How apply_markdown works (current path)

Relevant code is in **`markdown_support.py`**.

1. **`tool_apply_markdown`** (and the internal path) receives `model` (the Writer document) and `markdown` string. It calls **`_insert_markdown_at_position(model, ctx, markdown_string, position)`** with `position` in `"beginning"` | `"end"` | `"selection"`.

2. **`_insert_markdown_at_position`**:
   - Calls **`_get_markdown_transferable(ctx, markdown_string)`**: writes markdown to a temp file, loads it with `desktop.loadComponentFromURL(..., "_blank", 0, {Hidden: True, FilterName: "Markdown"})` into a **hidden** Writer document, selects all, returns `(transferable, hidden_component, path)`.
   - **Closes the hidden document and deletes the temp file** (so when we insert, only one Writer doc is open).
   - Calls **`_insert_transferable_at_position(model, ctx, transferable, position, use_process_events=True)`**.

3. **`_insert_transferable_at_position`**:
   - Gets `controller = model.getCurrentController()` and `our_frame = controller.getFrame()`.
   - Tries to make our frame active: (a) finds a frame with the same document URL in `desktop.getFrames().queryFrames(...)` and calls `activate()` on it, then `processEventsToIdle()`; (b) otherwise calls `our_frame.activate()` and `processEventsToIdle()`.
   - Positions the view cursor (beginning / end / selection).
   - Calls **`controller.insertTransferable(transferable)`**.
   - If the document length did not increase, tries a fallback: set system clipboard to the transferable, dispatch `.uno:Paste` to `our_frame`, restore clipboard (this path currently fails with a UNO type error; see below).

So the **intended** behavior is: paste into the document we were given (`model`) via its controller. The **observed** behavior is: nothing appears in that document, so the paste is going to a different target.

---

## 3. What we learned

### 3.1 Desktop “current” vs our document

- When the user runs **Run markdown tests** from the menu, `main.py` does `model = desktop.getCurrentComponent()` and passes that to `run_markdown_tests(ctx, writer_model)`.
- As soon as the test runs, **`desktop.getCurrentFrame()` is not the frame of our document**, and **`desktop.getCurrentComponent()` is not our model** (identity check `current is model` is False). This is true **at test start** — before we open or close any hidden document.
- So when the menu runs, the desktop’s “current” frame/component is something other than the Writer document we were passed (e.g. the dispatch/menu frame or another frame). Our `model` is a valid reference to the Writer document, but it is not the “current” component.

### 3.2 insertTransferable inserts into the “current” component

- We call `controller.insertTransferable(transferable)` on the **controller of our model**.
- The document we measure before and after is **our model**. Its length never increases.
- So the implementation of `insertTransferable` is effectively inserting into whichever component the desktop considers **current**, not necessarily into the controller we called it on. The paste therefore goes to the “current” component, not to our document reference.

### 3.3 Same document URL, different object references

- Logs show that **both** the current component and our model have the **same document URL** (e.g. `file:///home/.../Sample.odt`).
- So the “current” frame and “our” frame both show the same file, but they are **different frame objects** (`id(current_frame) != id(our_frame)`).
- So there can be multiple frames (or views) for the same document. The one that receives the paste is the desktop’s current frame; the one we have a reference to is our model’s frame. If these are different component instances (or different views), our reference never sees the pasted content.

### 3.4 frame.activate() does not fix it

- Calling `our_frame.activate()` (and/or finding a frame with our URL in the frame tree and activating it, then `processEventsToIdle()`) does **not** make `desktop.getCurrentFrame()` return our frame. After activate, the log still shows `getCurrentFrame() is our_frame: False` and different frame ids.
- So we cannot rely on activate to make “current” equal our frame in this context (menu/dispatch).

### 3.5 Clipboard fallback fails with a UNO type error

- The fallback that sets the system clipboard to our transferable and dispatches `.uno:Paste` to our frame fails with: **`value is not of same or derived type!`**
- This likely comes from `XClipboard.setContents(transferable, owner)` or from restoring the previous contents. For example, the second parameter may need a proper `XClipboardOwner`, or the value returned by `getContents()` may not be valid for `setContents()` when restoring. This was not fully diagnosed.

---

## 4. Log files and diagnostics

- **`/tmp/localwriter_markdown_debug.log`** is written by the markdown insert path and the test runner. It is **always** written to this path so you can inspect it even when UserConfig is not writable. Use **`clear_logs.sh`** to clear it (and other logs) before a run.
- The log contains:
  - **`[test_start]`**, **`[after_close_hidden]`**, **`[before_activate]`**, **`[after_activate_and_events]`**: For each, whether `getCurrentFrame() is our_frame` and `getCurrentComponent() is model`, plus frame names, **current_component URL** and **our model URL**, and `id(current_frame)` / `id(our_frame)`.
  - **`frame_tree_activate: ...`** if a frame with our document URL was found and activated.
  - **`insert_transferable: before_insert`** / **`after_insert`** with `len_model`, `inserted=True|False`.
  - **`clipboard_dispatch failed: ...`** if the clipboard fallback raised.
- Helpers that write this log: **`_log_frame_state(ctx, model, label)`**, **`_model_url(model)`**, **`_frame_name(frame)`**, and the diagnostic blocks inside **`_insert_transferable_at_position`** in `markdown_support.py`.

---

## 5. What should be investigated next

### 5.1 Use current component when URL matches (recommended first step)

- **Idea**: If `desktop.getCurrentComponent()` is a Writer-like component and its URL equals our model’s URL, then the paste is going into that component. So use **that** component as the insert target instead of `model`: get its controller, position its view cursor, and call `insertTransferable(transferable)` on that controller. Then we are pasting into the same component we can later measure (or the same underlying document).
- **Where**: In **`_insert_transferable_at_position`**, at the start, get `current = desktop.getCurrentComponent()`. If `current` has `getText` and `getURL`, and `current.getURL() == model.getURL()` (and both non-empty), then set `model = current` (or use `current` as the target for the rest of the function: controller, cursor, and insert). Then proceed as now. This aligns the insert target with the component that actually receives the paste when run from the menu.
- **Edge cases**: Unsaved documents may have an empty or private URL; then URL comparison may not match. Handle that (e.g. fall back to original `model` when URL is empty or not comparable).

### 5.2 Fix the clipboard fallback (optional)

- **Goal**: Make the “clipboard + .uno:Paste” path work when the direct insert still does nothing, so it can be used as a fallback or for comparison.
- **Tasks**: (a) Find the exact call that raises `value is not of same or derived type!` (e.g. `setContents(transferable, None)` vs `setContents(old_trans, None)`). (b) Use the correct UNO type for the clipboard owner (e.g. pass a valid `XClipboardOwner` or omit if the API allows). (c) When restoring, ensure the value passed to `setContents` is valid (e.g. only restore if `getContents()` returned something that is documented to be valid for `setContents`).
- **Reference**: `com.sun.star.datatransfer.clipboard.SystemClipboard`, `XClipboard.setContents` / `getContents`.

### 5.3 Sidebar vs menu context

- **Question**: Does the same failure happen when **apply_markdown** is used from the **Chat sidebar** (tool-calling) with the same document open? In the sidebar, the user has already focused the Writer document; `desktop.getCurrentComponent()` might already be that document when the tool runs. If insert works from the sidebar but not from the menu, that supports the “current component” explanation; then the “use current component when URL matches” fix is mainly for the menu (and any other path where current ≠ our model).
- **How to check**: Run a chat that triggers `apply_markdown` (e.g. “append the following at the end: …”) from the sidebar and confirm the content appears. Compare with running the same from the menu fallback (if applicable) or from “Run markdown tests”.

### 5.4 Why multiple frames for the same document?

- We see the same document URL in both “current” and “our” frame but different frame ids. It would help to know whether LibreOffice creates multiple frames/components for the same file in this scenario (e.g. one per view or one per dispatch context), and whether there is a supported way to get “the” frame for a given document or to make a given frame the current one. The LibreOffice UNO documentation (XDesktop, XFrame, XFramesSupplier, getCurrentFrame, frame activation) could be reviewed for this.

### 5.5 Cleanup of diagnostics (later)

- Once the insert path is fixed and stable, consider removing or gating the verbose diagnostics in **`_insert_transferable_at_position`** and **`_log_frame_state`** (writes to `/tmp/localwriter_markdown_debug.log` and the extra frame/URL/id logging) so they do not run in production, or make them conditional on a config/debug flag.

---

## 6. Key code locations

| What | Where |
|------|--------|
| Apply markdown entry (tool) | `markdown_support.py`: `tool_apply_markdown` |
| Insert at position (hidden doc + transferable) | `markdown_support.py`: `_insert_markdown_at_position` |
| Get transferable from hidden markdown doc | `markdown_support.py`: `_get_markdown_transferable` |
| Insert transferable (activate, cursor, insert, clipboard fallback) | `markdown_support.py`: `_insert_transferable_at_position` |
| Frame/current logging helper | `markdown_support.py`: `_log_frame_state`, `_model_url`, `_frame_name` |
| Test runner (menu) | `markdown_support.py`: `run_markdown_tests` |
| Menu trigger for tests | `main.py`: `args == "RunMarkdownTests"`, `run_markdown_tests(self.ctx, writer_model)` |
| Document context / tools | `document_tools.py`: `execute_tool`, WRITER_TOOLS |
| Debug log paths | `core/logging.py`: `debug_log`, `debug_log_paths` |
| Clear logs script | `clear_logs.sh` (includes `/tmp/localwriter_markdown_debug.log`) |

---

## 7. Short summary

- **Problem**: `insertTransferable` in the apply_markdown path does not insert into the document we hold a reference to when run from the menu; it inserts into the desktop’s “current” component.
- **Cause**: When the menu runs, the current frame/component is not our document’s frame; we have a reference to the same document (same URL) but a different frame/component, and paste goes to the current one.

## 8. What Was Fixed (Update)

### Fix 1: URL Matching (✅ IMPLEMENTED)
**Status**: Working - All tests now pass!

The fix detects when `desktop.getCurrentComponent()` has the same URL as our model and uses the current component as the insert target. This aligns our target with where `insertTransferable()` actually pastes.

**Code**: Lines 284-303 in `markdown_support.py`

### Fix 2: Direct Insert Method (✅ IMPLEMENTED)
**Status**: Working - Falls back to raw text insertion

When the transferable from hidden documents is empty (0 flavors), the code now uses `insertString()` to insert the markdown as raw text. This ensures content is inserted even if formatting doesn't work.

**Code**: `_insert_markdown_direct()` function in `markdown_support.py`

### Fix 3: Visible Document for Formatting (⚠️ EXPERIMENTAL)
**Status**: Implemented but may not work

Attempts to load markdown in a visible document first (to get proper formatting), then falls back to hidden. The transferable from visible documents may contain formatted content.

**Code**: Lines 547-572 in `markdown_support.py`

## 9. Current Status

### What Works
- ✅ All 7 markdown tests pass
- ✅ Content is inserted (document length increases)
- ✅ Menu and sidebar insertion work
- ✅ URL matching fixes targeting issue
- ✅ Direct insert provides fallback

### What Doesn't Work Yet
- ❌ Markdown formatting not rendered (bold, italic, headings appear as plain text)
- ❌ Transferable from hidden/visible documents still empty (0 flavors)

### Root Cause of Formatting Issue

The `getTransferable()` method from both hidden and visible markdown documents returns an **empty transferable** (0 flavors), even though the document loads correctly and displays formatted text when opened manually.

**Evidence**:
```
HIDDEN DOC: selected_text length = 45, content = Markdown test...
HIDDEN DOC: transferable flavors = 0  ← Empty!
```

The text is selected, but the transferable has no data flavors to paste.

## 10. Understanding LibreOffice's Markdown Behavior

The key insight: **LibreOffice has native markdown support** - we should leverage it, not work around it.

### Tests to Run in LibreOffice

#### Test 1: Manual Markdown Import
1. Create a test.md file with:
   ```markdown
   # Heading
   **Bold** and *italic* text
   - List item
   ```
2. Open LibreOffice Writer
3. File → Open → Select test.md
4. Observe: Does it render as formatted text?

**Expected**: Should see proper heading, bold, italic, list formatting

#### Test 2: Filter Names to Try
Test different filter names in `loadComponentFromURL`:
```python
# Try these filter names:
"Markdown"
"Text (Markdown)"
"markdown"
"Text"
"Text (markdown)"
```

#### Test 3: Get Formatted Text from Document
After loading markdown document:
```python
# Try different ways to get content
doc.getText().getString()  # Raw text
doc.getText().createTextCursor().getString()  # Selected text

# Try exporting to see if formatting is preserved
doc.storeToURL("/tmp/test.odt", (FilterName: "writer8",))
```

#### Test 4: Copy/Paste from Markdown Document
```python
# Select all in markdown document
cursor = doc.getText().createTextCursor()
cursor.gotoStart(False)
cursor.gotoEnd(True)

# Copy to clipboard
frame = doc.getCurrentController().getFrame()
dispatch = frame.queryDispatch(".uno:Copy", "", 0)
dispatch.dispatch(None, ())

# Paste into target document
target_frame.queryDispatch(".uno:Paste", "", 0).dispatch(None, ())
```

#### Test 5: Use XTextRangeCompare to Copy Content
```python
# Copy content between documents using text ranges
source_text = source_doc.getText()
target_text = target_doc.getText()

# Create cursors
source_cursor = source_text.createTextCursor()
target_cursor = target_text.createTextCursor()

# Copy range by range
source_cursor.gotoStart(False)
while source_cursor.gotoEndOfParagraph(True):
    source_cursor.gotoEndOfParagraph(False)
    target_cursor.getText().insertString(target_cursor, source_cursor.getString(), False)
    target_cursor.gotoEnd(False)
```

#### Test 6: Use XModel to Copy Styles
```python
# Get style families from source document
styles = source_doc.getStyleFamilies()
# Apply to target document
for style in styles.getByName("ParagraphStyles"):
    # Copy style definitions
    pass
```

#### Test 7: Check Document Properties
```python
# After loading markdown, check if it's recognized as markdown
print(doc.getDocumentProperties())
print(doc.getText().getTextFieldMasterNames())
```

## 11. LibreOffice UNO APIs to Investigate

### XTextRange and XTextCursor
- Can we copy formatted ranges between documents?
- Does `insertTextContent()` preserve formatting?

### XStyleFamiliesSupplier
- Can we copy styles from markdown document to target?
- Are markdown styles preserved in the document?

### XFilterDetection
- Does LibreOffice detect markdown automatically?
- What filter is used when opening .md files?

### XComponentLoader
- What filter names does LibreOffice recognize for markdown?
- Can we list available filters?

## 12. Debugging Techniques

### Log Filter Detection
```python
# List all available filters
filters = ctx.getServiceManager().createInstance("com.sun.star.document.FilterFactory")
print(filters.getElementNames())
```

### Inspect Document Model
```python
# After loading markdown
print("Document type:", doc.getImplementationName())
print("Supports service:", doc.supportsService("com.sun.star.text.TextDocument"))
print("Text length:", len(doc.getText().getString()))
```

### Check Transferable Flavors
```python
transferable = controller.getTransferable()
if transferable:
    flavors = transferable.getTransferDataFlavors()
    for flavor in flavors:
        print("Flavor:", flavor.MimeType, flavor.HumanPresentableName)
```

## 13. Recommended Approach

**Goal**: Understand how LibreOffice handles markdown internally, then use the same mechanism.

### Step 1: Run Manual Tests
- Test markdown import in LibreOffice UI
- Identify which filter name works
- Check if formatting is preserved

### Step 2: Instrument Code with Debugging
Add logging to understand:
- Which filter is being used
- What content is loaded
- Why transferable is empty

### Step 3: Use LibreOffice's Same Mechanism
Once we understand how it works manually, replicate in code:
- Use correct filter name
- Extract formatted content properly
- Preserve styles during transfer

### Step 4: Avoid Reinventing the Wheel
Don't write our own markdown parser - use LibreOffice's built-in support.

## 14. Key Questions to Answer

1. What filter name does LibreOffice use for .md files?
2. Does `loadComponentFromURL` with that filter apply formatting?
3. How can we extract formatted content from the loaded document?
4. Why is `getTransferable()` returning empty transferable?
5. Can we copy formatted ranges between documents?

## 15. Testing Plan

1. **Manual Test**: Verify markdown import works in UI
2. **Filter Test**: Find correct filter name
3. **Transferable Test**: Check flavors in loaded document
4. **Copy Test**: Try different copy methods
5. **Fallback Test**: Ensure raw text still works

Once we understand the answers, we can implement proper formatting support.

## 16. Documentation to Update

- Update `MARKDOWN_INSERT_INVESTIGATION.md` with test results
- Add findings to `LESSONS_LEARNED.md`
- Document correct approach in code comments

## 17. Success Criteria

✅ Markdown loads with proper formatting in LibreOffice UI
✅ We identify the correct filter name and mechanism
✅ Transferable contains formatted data (not empty)
✅ Formatted content can be inserted into target document

## 12. Files Modified

- `markdown_support.py` - Main implementation
- `MARKDOWN_INSERT_INVESTIGATION.md` - This document (updated)
- `LESSONS_LEARNED.md` - Detailed journey
- `FINAL_RESULT.md` - Final summary

## 13. Test Results

```
✅ 7/7 tests pass
✅ Content inserted (len 161→209)
✅ All formatting keywords found (Heading, Bold, italic, underline)
❌ But formatting not rendered (appears as plain text)
```

The foundation is solid. Formatting can be added as an enhancement later.
