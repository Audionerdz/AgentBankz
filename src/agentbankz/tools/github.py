"""GitHub repository analysis tools for AI engineer research."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field
from langchain_core.tools import tool

API_HEADERS: dict | None = None
GITHUB_API_URL = "https://api.github.com"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"

_MAX_FETCHED_FILE_CHARS = 60_000


def _get_headers() -> dict:
    global API_HEADERS
    if API_HEADERS is None:
        token = os.getenv("GITHUB_TOKEN") or os.getenv("github_token")
        API_HEADERS = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHubResearcher",
        }
        if token:
            API_HEADERS["Authorization"] = f"token {token}"
    return API_HEADERS


class ListRepoFilesInput(BaseModel):
    repo_url: str = Field(description="Full GitHub repository URL, for example https://github.com/owner/repo.")
    path: str = Field(default="", description="Repository directory path to list. Leave empty for the root.")


class FetchGithubFileInput(BaseModel):
    repo_url: str = Field(description="Full GitHub repository URL.")
    file_path: str = Field(description="Relative path to fetch, for example README.md or src/main.py.")


def parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url.strip())
    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() != "github.com" or len(path_parts) < 2:
        msg = f"Invalid GitHub repository URL: {repo_url}"
        raise ValueError(msg)
    owner, repo = path_parts[0], path_parts[1].removesuffix(".git")
    return owner, repo


def _detect_branch(owner: str, repo: str) -> str:
    try:
        response = httpx.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}",
            headers=_get_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json().get("default_branch", "main")
    except Exception:
        return "main"


def _fetch_file_content(
    owner: str, repo: str, path: str, branch: str | None = None
) -> str:
    try:
        resolved_branch = branch or _detect_branch(owner, repo)
        response = httpx.get(
            f"{GITHUB_RAW_URL}/{owner}/{repo}/{resolved_branch}/{path}",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.text
    except Exception as exc:
        return f"Error fetching file: {exc}"


def _list_directory_api(owner: str, repo: str, path: str = "") -> list[dict]:
    try:
        r1 = httpx.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}",
            headers=_get_headers(),
            timeout=15.0,
        )
        if r1.status_code == 200:
            data = r1.json()
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass

    try:
        branch = _detect_branch(owner, repo)
        r2 = httpx.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
            headers=_get_headers(),
            timeout=20.0,
        )
        r2.raise_for_status()
        tree = r2.json().get("tree", [])

        base = path.strip("/")
        items: dict[str, dict] = {}

        for entry in tree:
            epath = entry.get("path", "")
            etype = entry.get("type", "")
            if not epath:
                continue

            if not base:
                if "/" not in epath:
                    name = epath
                    items[name] = {
                        "name": name,
                        "path": epath,
                        "type": "dir" if etype == "tree" else "file",
                    }
                continue

            if not epath.startswith(base + "/") and epath != base:
                continue

            remainder = epath[len(base) + 1:] if epath.startswith(base + "/") else ""
            if remainder and "/" not in remainder:
                name = remainder
                items[name] = {
                    "name": name,
                    "path": epath,
                    "type": "dir" if etype == "tree" else "file",
                }

        return list(items.values())
    except Exception:
        return []


def _render_tree(items: list[dict], prefix: str = "", is_last: bool = True) -> str:
    if not items:
        return ""

    tree = ""
    for i, item in enumerate(items):
        is_last_item = i == len(items) - 1
        current_prefix = "└── " if is_last_item else "├── "
        name = item.get("name", "")
        item_type = item.get("type", "")

        emoji = "📁" if item_type == "dir" else "📄"
        tree += f"{prefix}{current_prefix}{emoji} {name}\n"

        if item_type == "dir" and i < 4:
            next_prefix = prefix + ("    " if is_last_item else "│   ")
            children = _list_directory_api(
                item.get("_owner", ""), item.get("_repo", ""), item.get("path", "")
            )
            if children:
                for child in children[:6]:
                    child["_owner"] = item.get("_owner", "")
                    child["_repo"] = item.get("_repo", "")
                tree += _render_tree([child], next_prefix, is_last_item)

    return tree


def _get_file_type(filename: str) -> str:
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "jsx",
        ".tsx": "tsx",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".txt": "text",
        ".sh": "bash",
        ".env": "bash",
    }
    _, ext = filename.rsplit(".", 1) if "." in filename else ("", "")
    return ext_map.get(f".{ext}", "text")


@tool(args_schema=ListRepoFilesInput)
def list_repo_files(repo_url: str, path: str = "") -> str:
    """Display directory tree structure of a GitHub repository.

    Shows the complete file and folder structure at the specified path,
    allowing the model to navigate and decide which files to investigate.

    Args:
        repo_url: Full GitHub repository URL (e.g., https://github.com/owner/repo)
        path: Specific directory path to explore (empty = root directory)

    Returns:
        Tree structure with directory and file names, types marked with emojis.
    """
    try:
        owner, repo = parse_github_repo_url(repo_url)
    except ValueError as exc:
        return str(exc)

    items = _list_directory_api(owner, repo, path)
    if not items:
        return f"Directory '{path}' not found or is empty."

    for item in items:
        item["_owner"] = owner
        item["_repo"] = repo

    display_path = f"{owner}/{repo}/{path}" if path else f"{owner}/{repo}"
    tree = f"📦 {display_path}/\n"
    tree += _render_tree(items)

    return tree


@tool(args_schema=FetchGithubFileInput)
def fetch_github_file(repo_url: str, file_path: str) -> str:
    """Fetch and display the complete content of a specific file.

    Navigate through the repository by fetching any file to inspect its
    contents. Useful for examining code, configuration, and documentation files.

    Args:
        repo_url: Full GitHub repository URL
        file_path: Relative path to the file (e.g., src/config.py, README.md)

    Returns:
        Complete file contents with syntax highlighting info based on file type.
    """
    try:
        owner, repo = parse_github_repo_url(repo_url)
    except ValueError as exc:
        return str(exc)

    content = _fetch_file_content(owner, repo, file_path)
    if content.startswith("Error"):
        return content

    original_length = len(content)
    was_truncated = original_length > _MAX_FETCHED_FILE_CHARS
    if was_truncated:
        content = content[:_MAX_FETCHED_FILE_CHARS]

    file_type = _get_file_type(file_path)
    result = f"## File: {file_path}\n\n"
    result += f"```{file_type}\n"
    result += content
    result += "\n```\n"
    if was_truncated:
        result += (
            f"\n[File truncated from {original_length} to "
            f"{_MAX_FETCHED_FILE_CHARS} characters to keep the agent stream stable.]\n"
        )

    return result
