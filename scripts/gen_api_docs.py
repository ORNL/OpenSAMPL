import ast
import shutil
import yaml
from pathlib import Path

PACKAGE_NAME = "opensampl"
SRC_DIR = Path(PACKAGE_NAME)
API_DIR_NAME = "api"
DOCS_API_DIR = Path("docs") / API_DIR_NAME
MKDOCS_YML = Path("mkdocs.yaml")

click_progname_map = {
    'opensampl.cli': 'opensampl',
    'opensampl.server.cli': 'opensampl-server'
}

def get_click_command_name(file_path: Path) -> str | None:
    """Extract the name of the main click command/group function."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr in {"command", "group"}:
                        return node.name
    return None

def is_click_command(file_path: Path) -> bool:
    """Heuristically determine if a Python file defines or registers click commands."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if dec.func.attr in {"command", "group"}:
                        return True

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {"add_command", "get_cli_command"}:
                    return True

    return False

def write_index_md(nav_structure):
    def build_markdown(nav, indent=0):
        lines = []
        indent_str = "    " * indent  # 4 spaces per level

        for item in nav:
            for label, value in item.items():
                if label == "index":
                    continue
                display = label.replace("_", " ").title()

                if isinstance(value, list):
                    lines.append(f"{indent_str}- {display}")
                    sub_lines = build_markdown(value, indent + 1)
                    if sub_lines:
                        lines.extend(sub_lines)
                else:
                    relative_link = value[len(f"{API_DIR_NAME}/"):] if value.startswith(f"{API_DIR_NAME}/") else value
                    lines.append(f"{indent_str}- [{display}]({relative_link})")

        return lines

    # Skip first entry if it's the index page
    content_lines = build_markdown(nav_structure[1:] if nav_structure and "index" in nav_structure[0] else nav_structure)

    content = (
        "# API Reference\n\n"
        "Welcome to the OpenSAMPL API documentation.\n\n"
        "Browse the modules and packages below:\n\n" +
        "\n".join(content_lines)
    )

    (DOCS_API_DIR / "index.md").write_text(content, encoding="utf-8")

def generate_api_docs_and_nav():
    if DOCS_API_DIR.exists():
        shutil.rmtree(DOCS_API_DIR)
    DOCS_API_DIR.mkdir(parents=True)

    nav_structure = [{"index": f"{API_DIR_NAME}/index.md"}]

    for py_file in sorted(SRC_DIR.rglob("*.py")):
        if py_file.stem == "__init__":
            continue
        rel_path = py_file.relative_to(SRC_DIR)
        doc_path = DOCS_API_DIR / rel_path.with_suffix(".md")
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        module_path = ".".join((PACKAGE_NAME,) + rel_path.with_suffix("").parts)
        is_click = is_click_command(py_file)

        if is_click:
            click_cmd = get_click_command_name(py_file) or "cli"
            content = (
                "# CLI Reference\n\n"
                "This page provides documentation for our command line tools.\n\n"
                "::: mkdocs-click\n"
                f"    :module: {module_path}\n"
                f"    :command: {click_cmd}\n"
                f"    :prog_name: {click_progname_map.get(module_path, click_cmd)}"
            )
        else:
            content = f"# `{module_path}`\n\n"
            content += f"::: {module_path}\n"
            content += "    options:\n"
            content += "      show_root_heading: false\n"
            content += "      show_submodules: true\n"
            content += "      show_source: true\n"

        doc_path.write_text(content, encoding="utf-8")

        # Update nav structure
        nav_entry = [nav_from_path(rel_path.with_suffix(".md"))]
        merge_nav_structures(nav_structure, nav_entry)
    # Create index.md for the API docs
    write_index_md(nav_structure)
    return nav_structure

def merge_nav_structures(base, new):
    """Merge two nested nav structures."""
    for new_item in new:
        for new_key, new_val in new_item.items():
            for base_item in base:
                if new_key in base_item:
                    # Merge recursively
                    if isinstance(base_item[new_key], list) and isinstance(new_val, list):
                        merge_nav_structures(base_item[new_key], new_val)
                    break
            else:
                base.append({new_key: new_val})

def nav_from_path(md_path: Path):
    parts = md_path.parts
    doc_title = parts[-1].replace(".md", "")
    nav_entry = {doc_title: f"{API_DIR_NAME}/{md_path.as_posix()}"}

    for part in reversed(parts[:-1]):
        nav_entry = {part: [nav_entry]}

    return nav_entry


def update_mkdocs_yml(nav_entries):
    with open(MKDOCS_YML, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Remove any existing 'API' section
    config["nav"] = [entry for entry in config.get("nav", []) if "API" not in entry]

    # Add updated API section
    config.setdefault("nav", []).append({"API": nav_entries})

    with open(MKDOCS_YML, "w", encoding="utf-8") as f:
        yaml.dump(config, f, sort_keys=False)

if __name__ == "__main__":
    nav_entries = generate_api_docs_and_nav()
    update_mkdocs_yml(nav_entries)
