# Formal Verification for WriterAgent

This document provides a tutorial, overview, and roadmap for applying formal verification techniques to the WriterAgent Python codebase.

## 1. Introduction to Formal Verification

Formal verification is the process of using mathematical proofs to verify that a system meets its specifications. Unlike traditional unit testing, which checks specific input/output pairs, formal verification aims to prove that a property holds for *all* possible inputs. If the property doesn't hold, the verifier provides a "counterexample"—a specific input that causes the failure.

### The Challenge of Verifying Python
Pure formal verification (like using Coq, TLA+, or Lean) is traditionally applied to statically-typed, compiled languages or specialized modeling languages. Python, being dynamically typed, heavily interpreted, and prone to "magic" (monkey-patching, metaclasses), is notoriously difficult to formally verify. Turning dynamic Python code into mathematical expressions (theorems) that an SMT solver (like Z3) can analyze is complex.

### The Challenge of Verifying LibreOffice (UNO)
WriterAgent's core functionality relies on LibreOffice's UNO API (Universal Network Objects). These objects are implemented in C++ and Java and are exposed to Python dynamically at runtime.
**No current Python formal verification tool can model or verify the behavior of arbitrary C++/UNO objects.**
Therefore, verification efforts must strictly isolate pure Python logic from UNO side-effects.

---

## 2. Tools for Python Verification

While full formal verification of Python is limited, several tools bridge the gap between testing and proofs:

### A. Deal & Deal-Solver
[`deal`](https://deal.readthedocs.io/) is a Python library for Design by Contract (DbC). It allows you to add decorators to functions specifying preconditions, postconditions, invariants, and expected exceptions.

```python
import deal

@deal.pre(lambda a, b: b != 0)
@deal.post(lambda result: result > 0)
def divide_positive(a: int, b: int) -> float:
    return a / b
```

`deal` has an experimental built-in formal verifier called `deal-solver` that converts these contracts and pure Python code into Z3 theorems.
*   **Pros:** Very strict, integrates directly with Python code via decorators.
*   **Cons:** Extremely limited scope. It only works for a tiny subset of Python (no loops, limited standard library, no mutability modeling). It will fail on most real-world WriterAgent code.

### B. CrossHair (Concolic Testing)
[`CrossHair`](https://crosshair.readthedocs.io/) is a "verifier-driven fuzzer" or concolic (concrete + symbolic) execution engine. It analyzes Python type hints and contracts (it supports `deal` contracts natively) and uses the Z3 SMT solver to intelligently search for inputs that violate the contracts or cause unhandled exceptions (like `IndexError` or `TypeError`).

*   **Pros:** Much more practical than pure verification. It executes the actual Python interpreter, so it supports most language features (loops, built-ins). It's excellent at finding edge cases you forgot to test.
*   **Cons:** It's incomplete—it might not prove a property holds forever (it times out), but it excels at finding counterexamples. It still cannot model external state (like a database or LibreOffice UNO objects).

### C. ESBMC-Python
[ESBMC](https://github.com/esbmc/esbmc) (Efficient SMT-based Context-Bounded Model Checker) is a mature bounded model checker originally for C/C++ that recently added a Python frontend. It transforms a Python AST into an intermediate representation and checks it with SMT solvers to find runtime errors (bounds checks, division by zero, user assertions).

*   **Pros:** Backed by a powerful, mature model checker. Great for verifying algorithmic correctness and low-level safety.
*   **Cons:** Requires type annotations. It simulates program execution up to a certain bound (depth), so it's not a full proof for infinite loops.

### D. PyVeritas
[PyVeritas](https://arxiv.org/html/2508.08171) is a novel approach that uses Large Language Models (LLMs) to transpile Python code into C code. It then uses existing, highly-optimized C bounded model checkers (like CBMC) on the generated code to find bugs and localize faults.
*   **Pros:** Leverages the maturity of C model checkers.
*   **Cons:** Highly experimental. The transpilation step assumes the Python code maps cleanly to C (no dynamic typing, eval, or UNO objects).

---

## 3. Roadmap for Incrementally Verifying WriterAgent

Given the architecture of WriterAgent, formal verification must be applied incrementally and selectively. You cannot run `deal prove` on `plugin/main.py`.

### Phase 1: Identify and Isolate Pure Logic
The first step is identifying modules that have **zero UNO dependencies** and operate only on pure Python types (strings, ints, lists, dicts).

Good candidates in WriterAgent:
*   `plugin/framework/url_utils.py` (URL string manipulation)
*   `plugin/modules/calc/address_utils.py` (Converting "A1" to column/row indices)
*   `plugin/framework/pricing.py` (Token math and floating-point cost calculations)

### Phase 2: Add Strict Type Hints and Contracts
To use any of these tools, the pure functions must be fully type-hinted. Next, add logical contracts (preconditions and postconditions) describing the exact expected behavior.

*Example for `plugin/modules/calc/address_utils.py`:*

```python
import deal

# Precondition: input must be uppercase letters
@deal.pre(lambda col_str: col_str.isalpha() and col_str.isupper())
# Postcondition: result is always >= 0
@deal.post(lambda result: result >= 0)
def column_to_index(col_str: str) -> int:
    result = 0
    for char in col_str:
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result - 1
```

### Phase 3: Apply CrossHair (Concolic Testing)
`CrossHair` is the most viable tool for immediate ROI on WriterAgent's pure logic.
1.  Install it: `pip install crosshair-tool`
2.  Run it on specific files: `crosshair check plugin/modules/calc/address_utils.py`
3.  CrossHair will analyze the type hints (e.g., `col_str: str`) and try to generate weird strings (empty strings, numbers, unicode) that crash `column_to_index` or violate the `@deal.post` condition.

You use CrossHair to *harden* your pure utility functions against edge cases.

### Phase 4: Refactor UNO Code for Testability (Hexagonal Architecture)
To verify code that currently touches LibreOffice, you must extract the decision-making logic away from the side-effects.

Instead of a function that reads a document, analyzes it, and writes back to it (which is un-verifiable), refactor it into three steps:
1.  **Read (UNO):** Extract text from LibreOffice.
2.  **Analyze (Pure Python):** A pure function that takes a string and returns a modified string. **(This function can now be formally verified/concolically tested).**
3.  **Write (UNO):** Push the modified string back to LibreOffice.

### Phase 5: Explore Bounded Model Checking (ESBMC-Python)
Once you have a robust suite of pure Python modules with assertions and contracts, you can experiment with `esbmc` to prove the absence of specific runtime errors (like division by zero or array out of bounds) up to a certain loop depth. This is particularly useful for complex algorithms, such as the `build_heading_tree` logic or the `error_detector` logic in Calc, assuming they can be fully isolated from UNO.

---

## 4. Summary

1.  **Don't try to verify UNO code.** Focus on pure Python modules.
2.  **Start with Type Hints and Contracts (`deal`).** Explicitly define what your utilities *should* do.
3.  **Use `CrossHair`** as an advanced, Z3-backed fuzzer to find counterexamples to your contracts.
4.  **Refactor** to push UNO side-effects to the edges of your architecture, leaving a verifiable, pure "core" of logic.
