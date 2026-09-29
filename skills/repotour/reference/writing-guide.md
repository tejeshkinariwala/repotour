# Writing guide

These rules apply to every string you put in `tour.yaml` and `notes.yaml`.

## 1. Plain, literal English

Say what the code does. Use the word the code uses. Do not use metaphors, similes or flourish, and do not judge the code ("elegant", "powerful", "robust", "clever").

| Avoid | Write |
|---|---|
| The heart of the system | Runs the main loop that processes each job |
| Glues the layers together | Calls the parser, then the validator, then the writer |
| A safety net for bad input | Rejects requests whose body does not match the schema |
| Handles all the heavy lifting | Converts each invoice to PDF |

If a literal phrase exists, use it.

## 2. Notes: one line, start with a verb

A note is one sentence, one line, no trailing detail about how it is implemented unless that is the point.

- "Checks one request body against one schema and returns the cleaned value."
- "Returns the user with this id, or None."
- "Raises with the list of bad fields."
- "Holds compiled schemas so each is parsed once."

Rules:

- Start with a verb in the third person: Checks, Returns, Creates, Reads, Writes, Sends, Raises, Holds, Registers, Parses.
- For a class, say what it holds or represents ("Holds...", "Wraps...", "Error raised when...").
- For a constant table or dispatch dict, say what maps to what: "Maps each command name to the function that runs it."
- Describe the behaviour, not the name. `get_user: Gets the user` says nothing.
- Mention side effects: writes files, sends network requests, mutates arguments, needs a lock.
- Private helpers get notes too, in the same style.
- Keys come from the outline JSON in `repotour scan --json`: top-level names, `Class.method` for methods, and nested children by their own bare name. Cover every item kind in the outline (functions, classes, methods, tables, types and interfaces, exported values). `consts` need no notes.
- Write `_file` for every non-test source file whose `header` in the scan output is not a useful one-line purpose. Headers are often poor: reST titles, license banners, copyright lines. One sentence, what the file is for and what it is not.
- Test files: notes are optional. A `_file` is enough.
- Quote a note that contains `: `, `#`, `{` or `[`.

## 3. Problems

A problem is what a newcomer would recognise as a real difficulty, phrased as the difficulty.

- Title: "A request can arrive with any shape of body". Not "Validation module".
- `without`: the concrete failure if this code did not exist. "Handlers would each parse the body themselves, and a missing field would surface as a KeyError deep in a handler."
- `fix`: how the files solve it and which files matter. "`validate.py` checks the body against a schema from `schemas/` and raises `ValidationError` with the list of bad fields. Handlers only see cleaned values."
- Every file belongs under exactly one problem (it may still appear in the steps of several stories). Ask "which problem is this file here to solve?" Put tests of that problem under `tests`.
- Aim for 2-6 problems per part. If a part has one problem holding 30 files, split it. If a problem holds one trivial file, merge it into a neighbour.

## 4. Parts

- 3-8 per repo. A part is an area a person can hold in their head: "API layer", "Storage", "Command line".
- `role` is one line: the job of the part. `summary` is 2-4 sentences.
- `folders` are used to place new files later. List real folder prefixes ending in `/` (`src/acme/api/`), never file paths.

## 5. Stories

A story follows one real use case through the code, in call order.

- Title says what a user does or what happens: "A user signs up", "The nightly job runs", "I add a new command".
- `command` is what starts it, when there is one: a CLI invocation, a `curl`, a test command. Omit it when there is none.
- Each step says what happens at that point and lists the files involved. Steps follow the order the code executes. Open the code and check the order.
- Name the functions or methods where it helps ("`create_user` calls `hash_password`").
- Include one story for the main path first. Then secondary paths: an error path, a background job, an extension point.
- 3-10 stories. Group with `act` when there are more than five.

## 6. Guide

A short reading order. Start with the map, then the main story, then the parts in dependency order (the parts others import last). Each item has a sentence of text.

## 7. Accuracy

- Never invent behaviour. If you did not read the code, do not describe it.
- If the code and its comments disagree, describe the code.
- If a claim depends on configuration, say so ("when `DEBUG` is set").
- Say what is missing or partial: "Today only `import` runs this check", "Retries are not implemented; the first failure ends the job", "Not covered by tests."
- Do not describe intended future behaviour as current behaviour.

## 8. Names in examples

When you need an example, use invented names ("Acme"). Do not put secrets, credentials, personal data or internal hostnames in any tour text, even if they appear in the code.

## 9. YAML

- Write every prose field (`summary`, `without`, `fix`, story `summary`, and step `text` that contains `: `) as a `>-` block scalar.
- Quote any other value that contains `: `, `#`, `{` or `[`.

## 10. Checklist before you build

- Every note starts with a verb and fits on one line.
- No metaphors, no praise words.
- Every problem has a `without` that names a failure and a `fix` that names files.
- Every story step follows the real call order.
- Honest gaps are stated.
- Every non-test source file has notes, and a `_file` if its header is not a useful purpose.
- The entry points and exports the README names appear in the outline and have notes. Report any the analyzer missed.
- Large repos (more than 300 files): one subagent per part writes the notes for that part's files, including a `_file` for tests only.
