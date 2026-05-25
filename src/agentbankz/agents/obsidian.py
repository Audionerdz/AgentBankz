OBSIDIAN_USAGE_GUIDE = """Rules for Obsidian vault:

## Available tools

  vault_list(path: str)               — List files and subdirectories in a vault directory
  vault_read(path: str)               — Read a file's content, frontmatter, tags, and stat
  vault_write(path: str, content: str) — Create or overwrite a vault file
  vault_append(path: str, content: str) — Append content to the end of a vault file
  vault_patch(path, target_type, target, operation, content) — Patch a heading, block, or frontmatter
  vault_delete(path: str)             — Delete a vault file
  vault_move(source: str, destination: str) — Move/rename a vault file
  vault_get_document_map(path: str)   — List headings, blocks, and frontmatter fields in a file
  active_file_get_path()              — Get the vault path of the currently open file
  periodic_note_get_path(period: str)  — Get path of daily/weekly/monthly/quarterly/yearly note
  search_simple(query: str)           — Full-text search across all notes
  search_query(query: dict)           — Structured JsonLogic search against metadata
  tag_list()                          — List all tags across the vault
  command_list()                      — List all registered Obsidian commands
  command_execute(command_id: str)    — Execute an Obsidian command by ID
  open_file(path: str)                — Open a file in the Obsidian UI

## Rules

- All paths are relative to the vault root (e.g. "notes/my-note.md")
- vault_write overwrites the entire file; use vault_append or vault_patch for partial edits
- vault_patch supports target_type: "heading", "block", "frontmatter"
- vault_patch operations: "append", "prepend", "replace"
- search_simple uses Obsidian's built-in fuzzy search
- search_query uses JsonLogic expressions against note metadata (frontmatter, tags, path, content)
- command_execute runs any command registered in Obsidian's command palette (use command_list first)
""".strip()