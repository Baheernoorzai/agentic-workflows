# Playbooks

Four reusable workflows for working with an AI coding agent on any project.
Each was run end to end on the expense tracker in this repo.

**Habits that apply to all four** (put them in the project's CLAUDE.md):
- Plan then act: investigate and propose first, wait for approval before changing anything.
- Small steps: one logical change at a time, with a way to verify it.
- Git save points: one logical change, one commit, and only when you say so.
- Stay in scope: list other problems you notice instead of fixing them.
- Explain briefly what was done and why.

---

## 1. Feature Development

**When to use it:** you want the software to do something new, and you can
describe the outcome in a sentence or two (a page, a field, a rule, a report).

**Steps**
1. Describe the feature and any rules. Ask for investigation and a short plan, no code.
2. Plan covers: files to change or add, data model change, new functions and routes, how it will be tested.
3. Build step 1: the logic in a testable module, with tests. Run them.
4. Build step 2: the web or UI layer, calling the logic. Add route tests.
5. Build step 3: sample data and docs.
6. Ask the agent to review its own change against the plan: missed edge cases, inconsistencies. Fix and add tests.
7. Commit each step.

**Human checkpoints**
- Approve or adjust the plan (this is where rules like "no budget means never flagged" get settled).
- After each step: read what changed, run the verify command, then approve the commit.
- After the self-review: decide which findings to fix now and which to defer.

**Prompt template**
```
Feature request: <feature>.
Rules: <rules and edge cases>.
Do NOT write code yet. Investigate the current code and give me a short PLAN:
files to change or add, data model change, new functions or routes, and how
you will test it. Keep business logic in <logic module>, not in the routes.
Wait for my approval. Then build in small steps; after each step tell me what
changed and how to verify it.
```

---

## 2. Bug Triage

**When to use it:** something that should work is wrong, and you have a symptom
but not a cause (a wrong total, a crash on some input, results that vary).

**Steps**
1. Paste the bug report. Say explicitly: do NOT fix yet.
2. Reproduce it with a small failing test using specific inputs. Run it and show the failure.
3. Explain the root cause: why exactly it happens, not just where.
4. Stop. Agree the diagnosis and the fix approach.
5. Apply the smallest correct fix for the root cause. No unrelated cleanup.
6. Run the failing test (now passing), then the whole suite.
7. Keep the test as a permanent regression test. Commit with a message naming the bug and the fix.

**Human checkpoints**
- After the reproduction: is this really the bug you reported?
- After the diagnosis: do you accept the explanation and the fix direction?
- After the fix: read the diff for size and scope before approving the commit.

**Prompt template**
```
Bug report: <bug report>.
Do NOT fix it yet. First REPRODUCE it: write a small failing test with specific
inputs that shows the wrong result. Then explain the ROOT CAUSE. Show me both
before proposing a fix. After I accept the diagnosis, apply the SMALLEST
correct fix, run the failing test and the full suite, and keep the test as a
regression test. List related issues you notice but do not fix them.
```

---

## 3. Refactoring

**When to use it:** the code works but is hard to read, change, or test, and
you want a cleaner structure with identical behavior (long functions, deep nesting).

**Steps**
1. Name the target. Do not change it. Ask for a step by step explanation, including quirks.
2. Write characterization tests that lock in current behavior, quirks included. Run them green.
3. Check the tests can fail: try a few deliberate mutations on a scratch copy.
4. Agree a list of small steps (extract a helper, flatten nesting, move a pass, rename).
5. Do one step at a time. After each, run the characterization tests and the full suite.
6. If any test fails: stop and report. Never edit the tests to make a step pass.
7. Compare old and new on many random inputs. Then commit.

**Human checkpoints**
- Review the characterization tests: do they capture what matters?
- Approve the step list.
- Any red test: decide with the agent whether the step was wrong.
- Decide later whether to fix the quirks (that is a separate piece of work).

**Prompt template**
```
Refactor <target module/function>. First do NOT change it. 1) Explain what it
does step by step, including quirks. 2) Write pytest characterization tests
that capture its CURRENT behavior, and show they pass. Then refactor in SMALL
steps (break it up, remove nesting, clear names, no behavior change). After
each step run the characterization tests and the full suite. If a step makes a
test fail, stop and tell me; do not change the test.
```

---

## 4. Analytics

**When to use it:** you have data and need answers, not software changes; the
output is findings a non technical reader can act on.

**Steps**
1. Explore the data read only: tables, columns, row counts, date range, categories, quality checks. No conclusions.
2. Propose 4 to 6 business questions the data can support. You pick.
3. Answer each with a query or small script. Show the query and the result. Sum money exactly (cents or Decimal).
4. Write a short insights summary for a manager.
5. Verify every figure a second, different way (raw rows, a different tool, the app itself). Fix any loose wording.
6. Save questions, queries, results, and the verified summary to a file. Commit.

**Human checkpoints**
- After exploration: is this the right data to be asking about?
- Choosing the questions.
- After verification: no figure goes in the summary unchecked.
- Read the caveats (synthetic data, small sample, how any plan figures were set).

**Prompt template**
```
Explore <data source> read only: tables, columns, row counts, date range,
categories. Summarize; no conclusions. Then I will pick from your proposed
questions: <questions>. For each, show the query you ran and the result. Write
a short insights summary for a non technical manager. Then recompute every
figure in it a different way and correct anything that does not reconcile.
Save it all to <analysis file> and wait for me to approve the commit.
```
