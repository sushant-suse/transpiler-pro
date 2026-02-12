# 🚀 Personal Transpiler-Pro

A high-fidelity documentation transpiler designed to convert **Markdown** into **Antora-compliant AsciiDoc**, specifically tailored for SUSE technical documentation standards.

## 📌 Project Overview

This project solves the "hallucination" and formatting breakage issues common in standard conversion tools (like Pandoc or kramdoc) when dealing with complex UI components like admonitions, collapsible blocks, and cross-references. It uses a **Three-Step Pipeline**:

1. **Pre-processing**: Shields complex Markdown components using unique text markers.
2. **Transpilation**: Utilizes `kramdoc` for standard element conversion (tables, headers, bold/italic).
3. **Post-processing**: Deterministically reconstructs protected components into perfect AsciiDoc syntax.

## 📂 Folder Structure

```text
.
├── src/transpiler_pro/
│   ├── core/
│   │   ├── converter.py    # Main engine: Pre/Post-processing & kramdoc wrapper
│   │   ├── linter.py       # Vale integration for SUSE style checking
│   │   ├── navigator.py    # (Planned) Directory traversal logic
│   │   └── fixer.py        # (Next Phase) Deterministic style repair
│   ├── utils/
│   │   └── paths.py        # Path management utilities
│   └── cli.py              # Typer-based Command Line Interface
├── styles/suse-styles/     # Official SUSE Vale rulesets and dictionaries
├── data/
│   ├── inputs/             # Source .md files
│   └── outputs/            # Transpiled .adoc files
└── tests/                  # Pytest suite for structural integrity
```

## ✨ Features Implemented (Phase 1)

### 1. Advanced Component Mapping

| Markdown | AsciiDoc (Antora) | Implementation Detail |
| --- | --- | --- |
| `:::info` / `:::tip` | `[IMPORTANT]` / `[TIP]` | Converts to full block delimiters (`====`) |
| `> **Note**:` | `[NOTE]` | Promotes blockquotes to formal Admonition blocks |
| `<details><summary>` | `[%collapsible]` | Preserves summary text as the block title |
| `[Title](./file.md)` | `xref:file.adoc[Title]` | Normalizes paths and strips leading `./` |
| `***bold-italic***` | `*_bold-italic_*` | Fixes complex nested formatting |

### 2. Structural Fixes

* **Header Protection**: Prevents syntax collisions by converting headers inside Admonitions into bold text.
* **List Normalization**: Fixes nesting depth in mixed lists (for example, numbered items inside bullets).
* **Path Sanitization**: Automatically strips redundant `./` from cross-references for Antora compliance.
* **Whitespace Management**: Collapses triple-newlines and ensures tight attribute-to-block alignment.

## 🛠 Installation & Usage

### Prerequisites

* [Python 3.13+](https://www.python.org/)
* [uv](https://github.com/astral-sh/uv) (Package manager)
* [kramdoc](https://github.com/asciidoctor/kramdown-asciidoc) (`gem install kramdown-asciidoc`)
* [Vale](https://vale.sh/) (Style linter)

### Setup

```bash
# Install dependencies
uv sync
```

### Running the Transpiler

To convert a single file and run the SUSE style linter:

```bash
uv run transpile run --file <filepath>
# Example
uv run transpile run --file data/inputs/test.md
```

Output will be saved as `data/outputs/` with a terminal report of any style violations.

## 🔍 Validation Workflow

The tool currently implements a **Convert-then-Lint** strategy:

1. **Conversion**: Generates the `.adoc` file in `data/outputs/`.
2. **Linting**: Automatically triggers **Vale** using the rules in `styles/suse-styles/`.
3. **Reporting**: Prints a color-coded report to the terminal identifying style violations (for example, `wifi` vs `Wi-Fi`, or use of future tense `will`).

---

1. admon.sh:
"
function admonitions_ds2ad {
  local f="$1"
python3 -c "
import re
import sys
ad_type_map = {
    'note': 'NOTE',
    'tip': 'TIP',
    'info': 'IMPORTANT',
    'warning': 'CAUTION',
    'caution': 'CAUTION',
    'danger': 'WARNING'
}
def admonition_ds2ad(adt):
    # Convert admonitions from Docusaurus to Asciidoctor
    # Named captures are e(everything), y(type), t(title), b(body)
    p = r'(?P<e>^(\s*):::(?P<y>\w+)(\n|\s|\[)(?P<t>.*?)(?<=\n)(?P<b>.*?)(^(\s*):::))'
    matches = re.finditer(p, adt, re.MULTILINE | re.DOTALL)
    for match in matches:
        ad_type = ad_type_map[match.group('y')]
        ad_title = match.group('t')
        if ad_title != '':
            ad_title = '.' + ad_title
            # Next line is a bit of a bodge as I can't find the regex to
            # both match and exclude the closing ']'
            ad_title = re.sub(r']', '', ad_title)
        ad_body = match.group('b')
        adt = adt.replace(match.group('e'),
                          f'\n[{ad_type}]\n{ad_title}====\n{ad_body}====\n')
    return adt
def main():
    if len(sys.argv) != 2:
        print('Usage: python admon.py input.md')
        sys.exit(1)
    md_file = sys.argv[1]
    with open(md_file, 'r', encoding='utf-8') as f:
        md_in = f.read()
        f.close()
    md_out = admonition_ds2ad(md_in)
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_out)
        f.close()
if __name__ == '__main__':
    main()
" "$f"
}
admonitions_ds2ad "$1"
#Convert DS admonitions to AD admonitions
"

2. collapsible_block.sh
"
function collapsible_blocks_ds2ad {
local f="$1"
python3 -c "
import re
import sys
def replace_match(match):
    summary_text = match.group(1)
    detail_content = match.group(2).strip()
    return f\".{summary_text}\n[%collapsible]\n======\n{detail_content}\n======\"
def collapsible_blocks_ds2ad(adt):
    # Convert collapsible blocks from Docusaurus to Asciidoctor
    pattern = re.compile(r'<details(?:\s+id=\"[^\"]+\")?>\s*<summary>([^<]+)</summary>\s*([\s\S]*?)\s*</details>')
    modified_content = pattern.sub(replace_match, adt)
    return modified_content
def main():
    if len(sys.argv) != 2:
        print('Usage: python admon.py input.md')
        sys.exit(1)
    ip_file = sys.argv[1]
    with open(ip_file, 'r', encoding='utf-8') as f:
        md_in = f.read()
        f.close()
    md_out = collapsible_blocks_ds2ad(md_in)
    with open(ip_file, 'w', encoding='utf-8') as f:
        f.write(md_out)
        f.close()
if __name__ == '__main__':
    main()
" "$f"
}
collapsible_blocks_ds2ad "$1"
#Convert DS collapsible blocks to AD collapsible blocks
"

3. convert.sh:
"
shopt -s globstar
rm -rf ./kramdown_md_to_asciidoc && \
mkdir -p ./kramdown_md_to_asciidoc && \
mkdir -p ./kramdown_md_to_asciidoc/i18n/zh/docusaurus-plugin-content-docs && \
cp -r ./docs ./shared-files ./sidebars.js ./versioned_docs ./versioned_sidebars ./kramdown_md_to_asciidoc
cp -r ./i18n/zh/docusaurus-plugin-content-docs ./kramdown_md_to_asciidoc/i18n/zh
find ./kramdown_md_to_asciidoc -type f \( -name "*.md" -o -name "*.mdx" \) -exec sh -c 'echo Processing Head tag in file $1 & head_tag.sh "$1" "antora"' _ {} \;
find ./kramdown_md_to_asciidoc -type f -name "*.md" -exec sh -c 'echo Replacing Collapsible blocks in file $1 & collapsible_block.sh "$1" ' _ {} \;
find ./kramdown_md_to_asciidoc -type f -name "*.md" -exec sh -c 'echo Converting file $1 & kramdoc -o "${1%.md}.adoc" "$1"' _ {} \;
find ./kramdown_md_to_asciidoc -type f -name "*.adoc" -exec sh -c 'echo Replacing Tabs in file $1 & tabs.sh "$1" ' _ {} \;
find ./kramdown_md_to_asciidoc -type f -name "*.adoc" -exec sh -c 'echo Replacing Admonitions in file $1 & admon.sh "$1" ' _ {} \;
find ./kramdown_md_to_asciidoc -type f -name "*.adoc" -exec sh -c 'echo Replacing cross reference links in file "$1" && sed -i "s|\\(link:[^ ]*\\)\\.md|\\1.adoc|g" "$1"' _ {} \;
find ./kramdown_md_to_asciidoc -type f \( -name "*sidebars.js" -o -name "*sidebars.json" \) -exec sh -c 'echo Converting sidebar file "$1" && python3 /usr/local/bin/nav.py "$1"' _ {} \;
rm ./kramdown_md_to_asciidoc/**/*.md
rm ./kramdown_md_to_asciidoc/**/sidebars*.js
rm ./kramdown_md_to_asciidoc/**/*sidebars.json
"

4. head_tag.sh:
"
# $1 = FILE
# $2 = TARGET (antora or daps) 
# $3 = DOMAIN (OPTIONAL)
# e.g. sh process_head_tag.sh docs/file.md antora
# e.g. sh process_head_tag.sh docs/file.md daps https://example.com
function process_head_tag {
  local f="$1"
  local a="$2"
  local d="$3"
ruby -e '
for_antora = ARGV[1]=="antora" ? true : false
process_head_tag(ARGV[0], for_antora)
BEGIN {
  # Antora: only removes <head> tag and its contents
  # Other: remove <head> tag and move its contents into a docfile, <file>-docinfo.html
  def process_head_tag(file, for_antora)
    new_file = []
    new_docinfo_file = []
    docinfo_filename = file.sub(/\.md[x]*$/,"-docinfo.html")
    docinfo_enabler = %{:docinfo: private-head
}
    parsing_head_tag = false
    File.foreach(file).with_index do |line, line_num|
      if parsing_head_tag
        if line.strip.include?("</head>")
          parsing_head_tag = false
          File.write(docinfo_filename, new_docinfo_file.join) if !for_antora
        elsif !for_antora
          if line.strip.include?("rel=\"canonical\"")
            domain = !ARGV[2].empty? ? ARGV[2].chomp("/") : "NEW_BASEURL"
            new_line = line.sub(/href=\".*\.com/, "href=\""+domain)
            new_docinfo_file << new_line
          else
            new_docinfo_file << line.strip
          end
        end
      else
        if line.strip.include?("<head>")
          new_file << docinfo_enabler if !for_antora
          parsing_head_tag = true
        else
          new_file << line
        end
      end
    end
    File.write(file, new_file.join)
  end
}
' "$f" "$a" "$d"
}
process_head_tag "$1" "$2" "$3"
"
5. tabs.sh:
"
function tabs_ds2ad {
local f="$1"
python3 -c "
import re
import sys
def tabs_ds2ad(adt):
    # Convert tabs from Docusaurus to Asciidoctor
    replacements = [
        (r'(\+)*<Tabs>(\+)*', '\n\n[tabs]\n======'),
        (r'(\+)*<Tabs groupId=\"([^\"]+)\">(\+)*', r'\n\n[tabs,sync-group-id=\\2]\n======'),
        (r'======(\+)*<TabItem value=\"([^\"]+)\" label=\"([^\"]+)\"( default=\"\")?>(\+)*', r'======\nTab \\3::\n+\n'),
        (r'======(\+)*<TabItem value=\"([^\"]+)\"( default=\"\")?>(\+)*', r'======\nTab \\2::\n+\n'),
        (r'(\+)*<TabItem value=\"([^\"]+)\" label=\"([^\"]+)\"( default=\"\")?>(\+)*', r'\n\nTab \\3::\n+\n'),
        (r'(\+)*<TabItem value=\"([^\"]+)\"( default=\"\")?>(\+)*', r'\n\nTab \\2::\n+\n'),
        (r'(\+)*</TabItem>(\+)*', ''),
        (r'(\+)*</Tabs>(\+)*', '\n======')
    ]
    for pattern, replacement in replacements:
        adt = re.sub(pattern, replacement, adt)
    return adt
def main():
    if len(sys.argv) != 2:
        print('Usage: python admon.py input.md')
        sys.exit(1)
    ip_file = sys.argv[1]
    with open(ip_file, 'r', encoding='utf-8') as f:
        md_in = f.read()
        f.close()
    md_out = tabs_ds2ad(md_in)
    with open(ip_file, 'w', encoding='utf-8') as f:
        f.write(md_out)
        f.close()
if __name__ == '__main__':
    main()
" "$f"
}
tabs_ds2ad "$1"
#Convert DS tabs to AD tabs (https://github.com/asciidoctor/asciidoctor-tabs)
"
---
nav.py:
"
import json
import re
import sys
import os
def extract_json_from_js(js_content):
    no_comments = re.sub(r'^\s*//.*\n?', '', js_content, flags=re.MULTILINE)
    json_match = re.search(r'const sidebars = (\{.*\n(?:.|\n)*?\})', no_comments, re.DOTALL)
    if json_match:
        json_str = re.sub(r'(\w+):', r'"\1":', json_match.group(1)).replace('\n', '').replace("'", '"')
        json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
        return json.loads(json_str)
    return None
def does_doc_file_contain_title_slug(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
        pattern = re.compile(r'^title:\s+.+', re.MULTILINE)
        match = pattern.search(content)
        if match:
            return True
        else:
            return False
    else:
        return False
def format_item(base_path, prefix, label, link_id=None):
    if link_id:
        root, ext = os.path.splitext(link_id)
        file_path = base_path + "/" + root + ".md"
        if(does_doc_file_contain_title_slug(file_path)):
            return f"{prefix}xref:{link_id}.adoc[]"
        else:
            return f"{prefix}xref:{link_id}.adoc[{label}]"
    return f"{prefix}{label}"
def process_items(base_path, items, depth=1):
    result = []
    prefix = '*' * depth + ' '
    for item in items:
        if isinstance(item, str):
            result.append(format_item(base_path, prefix, item.split('/')[-1].replace('-', ' ').title(), item))
        elif isinstance(item, dict):
            label = item.get('label', 'Category')
            if 'link' in item:
                result.append(format_item(base_path, prefix, label, item['link']['id']))
            if 'items' in item:
                if 'link' not in item:
                    result.append(format_item(base_path, prefix, label))
                result.extend(process_items(base_path, item['items'], depth + 1))
    return result
def main():
    if len(sys.argv) != 2:
        print('Usage: python nav.py sidebar.js')
        sys.exit(1)
    if "versioned_" in sys.argv[1]:
        base_path = "./kramdown_md_to_asciidoc/versioned_docs/" + os.path.splitext(os.path.basename(sys.argv[1]))[0]
    else:
        base_path = "./kramdown_md_to_asciidoc/docs"
    sidebar_path = sys.argv[1]
    nav_path = os.path.splitext(sidebar_path)[0] + '.adoc'
    with open(sidebar_path, 'r', encoding='utf-8') as f:
        if "versioned_" in sys.argv[1]:
            sidebar = json.loads(f.read())
        else:
            sidebar = extract_json_from_js(f.read())
    nav_content = []
    for key, sections in sidebar.items():
        nav_content.extend(process_items(base_path, sections))
    with open(nav_path, 'w') as f:
        f.write("\n".join(nav_content))
if __name__ == '__main__':
    main()
"
---
Dockerfile:
"
FROM ruby:3.1.5-slim-bullseye
RUN apt-get update && \
    apt-get install -y curl && \
    apt-get install -y python3 python3-pip && \
    apt-get -y autoclean
RUN gem install kramdown-asciidoc
COPY convert.sh admon.sh collapsible_block.sh head_tag.sh nav.py tabs.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/convert.sh \
             /usr/local/bin/admon.sh \
             /usr/local/bin/collapsible_block.sh \
             /usr/local/bin/head_tag.sh \
             /usr/local/bin/nav.py \
             /usr/local/bin/tabs.sh
WORKDIR /workspace
CMD ["convert.sh", "/workspace"]
"