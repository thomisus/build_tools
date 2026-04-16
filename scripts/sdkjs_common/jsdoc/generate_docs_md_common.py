import os
import json
import re
from pathlib import PurePosixPath

# ─── Global state ─────────────────────────────────────────────────────────────
missing_examples = []
used_enumerations = set()
translations = {}
translations_lang = None
missed_translations = {}
used_translations_keys = {}
global_output_dir = ""
cur_editor_name = None

# ─── File I/O ─────────────────────────────────────────────────────────────────

def find_common_path_part(path_full: str, path_suffix: str, anchor: str) -> str:
    path_full = path_full.replace('\\', '/')
    path_suffix = path_suffix.replace('\\', '/')

    parts1 = PurePosixPath(path_full).parts
    parts2 = PurePosixPath(path_suffix).parts

    try:
        idx1 = [p.lower() for p in parts1].index(anchor.lower())
        idx2 = [p.lower() for p in parts2].index(anchor.lower())
    except ValueError:
        return ""

    common_segments = []
    for p1, p2 in zip(parts1[idx1:], parts2[idx2:]):
        if p1.lower() == p2.lower():
            common_segments.append(p1)
        else:
            break

    return "/".join(common_segments)

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_markdown_file(file_path, content):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as md_file:
        md_file.write(content)

# ─── Text utilities ───────────────────────────────────────────────────────────

def remove_js_comments(text):
    text = re.sub(r'^\s*//.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    return text.strip()

def remove_line_breaks(string):
    return re.sub(r'[\r\n]+', ' ', string)

def convert_jsdoc_array_to_ts(type_str: str) -> str:
    """Recursively replaces 'Array.<T>' with 'T[]'."""
    pattern = re.compile(r'Array\.<([^>]+)>')
    while True:
        match = pattern.search(type_str)
        if not match:
            break
        inner_type = match.group(1).strip()
        inner_type = convert_jsdoc_array_to_ts(inner_type)
        type_str = type_str[:match.start()] + f"{inner_type}[]" + type_str[match.end():]
    return type_str

def get_base_type(ts_type: str) -> str:
    while ts_type.endswith('[]'):
        ts_type = ts_type[:-2]
    return ts_type

def escape_brackets_in_quotes(text: str) -> str:
    return re.sub(
        r"(['\"])(.*?)(?<!\\)\1",
        lambda m: m.group(1)
                  + m.group(2).replace('[', r'\[').replace(']', r'\]')
                  + m.group(1),
        text
    )

def escape_text_outside_code_blocks(markdown: str) -> str:
    """Escapes MDX-unsafe characters (<, >, {, }) outside fenced code blocks."""
    parts = re.split(r'(```.*?```)', markdown, flags=re.DOTALL)
    for i in range(0, len(parts), 2):
        text = (parts[i]
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('{', '&#123;')
                .replace('}', '&#125;'))
        parts[i] = escape_brackets_in_quotes(text)
    return "".join(parts)

# ─── i18n ─────────────────────────────────────────────────────────────────────

def get_translation(key):
    def process_part(k):
        if k not in translations:
            missed_translations[k] = k
        else:
            used_translations_keys[k] = True
        return translations.get(k, k)

    if '\\\n' in key:
        parts = key.split('\\\n')
        translated_parts = [process_part(p) for p in parts]
        return '\\\n'.join(translated_parts)

    return process_part(key)

# ─── Markdown link processing ─────────────────────────────────────────────────

def process_link_tags(text, root='', enum_file_prefix=''):
    """
    Replaces {@link ...} with Markdown links:
      global#Typedef  → Enumeration/{enum_file_prefix}Typedef.md
      Class#Method    → Class/Methods/Method.md
      /docs/...       → absolute docs path

    enum_file_prefix — prepended to typedef file names, e.g. 'Event_' for plugin events.
    """
    def replace_link(match):
        content = match.group(1).strip()
        parts = content.split()
        ref = parts[0]
        label = parts[1] if len(parts) > 1 else None

        if ref.startswith('/docs/'):
            url = root + '../../../..' + ref
            display_text = label if label else ref
            if url.endswith('/'):
                last_dir = url.rstrip('/').split('/')[-1]
                url = f"{url}{last_dir}"
            return f"[{display_text}]({url}.md)"
        elif ref.startswith("global#"):
            typedef_name = ref.split("#")[1]
            used_enumerations.add(typedef_name)
            display_text = label if label else typedef_name
            return f"[{display_text}]({root}Enumeration/{enum_file_prefix}{typedef_name}.md)"
        else:
            try:
                class_name, method_name = ref.split("#")
            except ValueError:
                return match.group(0)
            display_text = label if label else ref
            return f"[{display_text}]({root}{class_name}/Methods/{method_name}.md)"

    return re.sub(r'{@link\s+([^}]+)}', replace_link, text)

def correct_description(string, root='', isInTable=False, enum_file_prefix=''):
    if string is None:
        return get_translation('No description provided.')

    if not isInTable:
        string = string.replace('\r', '\\\n')
        string = re.sub(r'<b>', '-**', string)
    else:
        string = re.sub(r'<b>', '**', string)
        string = remove_line_breaks(string)

    string = re.sub(r'</b>', '**', string)
    string = re.sub(r'<note>(.*?)</note>', r'💡 \1', string, flags=re.DOTALL)
    string = process_link_tags(string, root, enum_file_prefix)

    return get_translation(string)

def correct_default_value(value, enumerations, classes, root='../'):
    if value is None or value == '':
        return ''
    if isinstance(value, bool):
        value = "true" if value else "false"
    else:
        value = str(value)
    return generate_data_types_markdown([value], enumerations, classes, root)

# ─── Type formatting ──────────────────────────────────────────────────────────

def generate_data_types_markdown(types, enumerations, classes, root='../', enum_file_prefix=''):
    """
    1) Converts each type from JSDoc (e.g., Array.<T>) to T[].
    2) Processes union types by splitting them using '|'.
    3) Supports multidimensional arrays, e.g., (string|ApiRange|number)[].
    4) If the base type matches the name of an enumeration or class, generates a link.
    5) The final types are joined using " | ".

    enum_file_prefix — prepended to enumeration file names and link labels,
                       e.g. 'Event_' for plugin events. When set, class linking is skipped.
    """
    converted = [convert_jsdoc_array_to_ts(t) for t in types]

    primitive_types = {"string", "number", "boolean", "null", "undefined", "any", "object",
                       "false", "true", "json", "function", "date", "{}"}

    def is_primitive(t):
        return (t.lower() in primitive_types or
                (t.startswith('"') and t.endswith('"')) or
                (t.startswith("'") and t.endswith("'")) or
                t.replace('.', '', 1).isdigit() or
                (t.startswith('-') and t[1:].replace('.', '', 1).isdigit()))

    def link_if_known(ts_type):
        ts_type = ts_type.strip()
        array_dims = 0
        while ts_type.endswith("[]"):
            array_dims += 1
            ts_type = ts_type[:-2].strip()

        # Process generic types, e.g., Object.<string, editorType>
        if ".<" in ts_type and ts_type.endswith(">"):
            m = re.match(r'^(.*?)\.<(.*)>$', ts_type)
            if m:
                base_part = m.group(1).strip()
                generic_args_str = m.group(2).strip()
                found = False
                for enum in enumerations:
                    if enum['name'] == base_part:
                        used_enumerations.add(base_part)
                        base_result = f"[{enum_file_prefix}{base_part}]({root}Enumeration/{enum_file_prefix}{base_part}.md)"
                        found = True
                        break
                if not found:
                    if enum_file_prefix:
                        base_result = base_part
                    elif base_part in classes:
                        base_result = f"[{base_part}]({root}{base_part}/{base_part}.md)"
                    elif is_primitive(base_part):
                        base_result = base_part
                    elif cur_editor_name == "forms":
                        base_result = f"[{base_part}]({root}../text-document-api/{base_part}/{base_part}.md)"
                    else:
                        print(f"Unknown type encountered: {base_part}")
                        base_result = base_part
                generic_args = [link_if_known(x) for x in generic_args_str.split(",")]
                result = base_result + ".&lt;" + ", ".join(generic_args) + "&gt;"
                result += "[]" * array_dims
                return result

        # Process union types enclosed in parentheses
        if ts_type.startswith("(") and ts_type.endswith(")"):
            inner = ts_type[1:-1].strip()
            subtypes = [sub.strip() for sub in inner.split("|")]
            if len(subtypes) == 1:
                result = link_if_known(subtypes[0])
            else:
                processed = [link_if_known(subtype) for subtype in subtypes]
                result = "(" + " | ".join(processed) + ")"
            result += "[]" * array_dims
            return result

        # Base type
        else:
            base = ts_type
            found = False
            for enum in enumerations:
                if enum['name'] == base:
                    used_enumerations.add(base)
                    result = f"[{enum_file_prefix}{base}]({root}Enumeration/{enum_file_prefix}{base}.md)"
                    found = True
                    break
            if not found:
                if enum_file_prefix:
                    result = base
                elif base in classes:
                    result = f"[{base}]({root}{base}/{base}.md)"
                elif is_primitive(base):
                    result = base
                elif cur_editor_name == "forms":
                    result = f"[{base}]({root}../text-document-api/{base}/{base}.md)"
                else:
                    print(f"Unknown type encountered: {base}")
                    result = base
            result += "[]" * array_dims
            return result

    linked = [link_if_known(ts_t) for ts_t in converted]
    param_types_md = r' | '.join(linked)
    param_types_md = param_types_md.replace("|", r"\|")

    def replace_leftover_generics(match):
        return f"&lt;{match.group(1).strip()}&gt;"

    param_types_md = re.sub(r'<([^<>]+)>', replace_leftover_generics, param_types_md)
    return param_types_md

def generate_properties_markdown(properties, enumerations, classes, root='../', enum_file_prefix=''):
    if properties is None:
        return ''

    content = f"\n\n## {get_translation('Properties')}\n\n"
    content += f"| {get_translation('Name')} | {get_translation('Type')} | {get_translation('Description')} |\n"
    content += "| ---- | ---- | ----------- |"

    for prop in sorted(properties, key=lambda m: m['name']):
        prop_name = prop['name']
        prop_description = prop.get('description', 'No description provided.')
        prop_description = correct_description(prop_description, root, isInTable=True, enum_file_prefix=enum_file_prefix)
        prop_types = prop['type']['names'] if prop.get('type') else []
        param_types_md = generate_data_types_markdown(prop_types, enumerations, classes, root, enum_file_prefix)
        content += f"\n| {prop_name} | {param_types_md} | {prop_description} |"

    return escape_text_outside_code_blocks(content)

def generate_class_markdown(class_name, methods, properties, enumerations, classes,
                            augments=None, path_to_methods='./'):
    """
    augments      — list of parent class names for subclass description (office-api only).
    path_to_methods — path prefix for method links in the table:
      './'        flat structure (plugins):    Methods/Methods.md links to ./MethodName.md
      './Methods/' nested structure (office-api): ClassName.md links to ./Methods/MethodName.md
    """
    if augments:
        extends_links = []
        for parent in augments:
            if parent in classes:
                extends_links.append(f"[{parent}](../{parent}/{parent}.md)")
            elif cur_editor_name == "forms":
                extends_links.append(f"[{parent}](../../text-document-api/{parent}/{parent}.md)")
            else:
                extends_links.append(parent)
        description = get_translation(f"{class_name} is a subclass of {', '.join(extends_links)}.")
    else:
        description = get_translation(f"Represents the {class_name} class.")

    content = f"# {class_name}\n\n{description}"
    content += generate_properties_markdown(properties, enumerations, classes)

    content += f"\n\n## {get_translation('Methods')}\n\n"
    content += f"| {get_translation('Method')} | {get_translation('Returns')} | {get_translation('Description')} |\n"
    content += "| ------ | ------- | ----------- |\n"

    for method in sorted(methods, key=lambda m: m['name']):
        method_name = method['name']

        returns = method.get('returns', [])
        if returns:
            return_type_list = returns[0].get('type', {}).get('names', [])
            returns_markdown = generate_data_types_markdown(return_type_list, enumerations, classes, '../')
        else:
            returns_markdown = get_translation('None')

        description = correct_description(method.get('description', 'No description provided.'), '../', True)
        method_link = f"[{method_name}]({path_to_methods}{method_name}.md)"

        content += f"| {method_link} | {returns_markdown} | {description} |\n"

    return escape_text_outside_code_blocks(content)

def generate_enumeration_markdown(enumeration, enumerations, classes, example_editor_name='', enum_file_prefix=''):
    enum_name = enumeration['name']

    if enum_name not in used_enumerations:
        return None

    description = enumeration.get('description', 'No description provided.')
    description = correct_description(description, '../', enum_file_prefix=enum_file_prefix)

    content = f"# {enum_file_prefix}{enum_name}\n\n{description}"

    parsed_type = enumeration['type'].get('parsedType')
    if not parsed_type:
        type_names = enumeration['type'].get('names', [])
        if type_names:
            content += f"\n\n## {get_translation('Type')}\n\n"
            content += generate_data_types_markdown(type_names, enumerations, classes, enum_file_prefix=enum_file_prefix)
    else:
        ptype = parsed_type['type']

        if ptype == 'TypeUnion':
            content += f"\n\n## {get_translation('Type')}\n\n{get_translation('Enumeration')}"
            content += f"\n\n## {get_translation('Values')}\n\n"
            if enum_file_prefix:
                for raw_t in enumeration['type']['names']:
                    if any(enum['name'] == raw_t for enum in enumerations):
                        used_enumerations.add(raw_t)
                        content += f"- [{raw_t}](../Enumeration/{enum_file_prefix}{raw_t}.md)\n"
                    else:
                        content += f"- {raw_t}\n"
            else:
                enum_empty = True
                for raw_t in enumeration['type']['names']:
                    ts_t = convert_jsdoc_array_to_ts(raw_t)
                    if any(enum['name'] == raw_t for enum in enumerations):
                        used_enumerations.add(raw_t)
                        content += f"- [{ts_t}](../Enumeration/{raw_t}.md)\n"
                        enum_empty = False
                    elif raw_t in classes:
                        content += f"- [{ts_t}](../{raw_t}/{raw_t}.md)\n"
                        enum_empty = False
                    elif ts_t.find('Api') == -1:
                        content += f"- {ts_t}\n"
                        enum_empty = False
                if enum_empty:
                    return None

        elif ptype == 'TypeApplication':
            content += f"\n\n## {get_translation('Type')}\n\n"
            type_names = enumeration['type'].get('names', [])
            if type_names:
                t_md = generate_data_types_markdown(type_names, enumerations, classes, enum_file_prefix=enum_file_prefix)
                if t_md.endswith('[]'):
                    content += f"{get_translation('array')}"
                else:
                    content += f"{get_translation('object')}"
        elif ptype not in ('TypeUnion', 'TypeApplication'):
            type_names = enumeration['type'].get('names', [])
            if type_names:
                content += f"\n\n## {get_translation('Type')}\n\n"
                content += generate_data_types_markdown(type_names, enumerations, classes, enum_file_prefix=enum_file_prefix)
                
        # Explicit properties check under any ptype
        if enumeration.get('properties') is not None:
            content += generate_properties_markdown(enumeration['properties'], enumerations, classes, enum_file_prefix=enum_file_prefix)

    content += generate_example_markdown(enumeration.get('example', ''), example_editor_name)

    return escape_text_outside_code_blocks(content)

def generate_method_markdown(method, enumerations, classes, root='../', example_editor_name=''):
    """
    Generates Markdown for a method doclet.

    root controls path depth for all internal links:
      '../'   — flat structure (plugins):    Methods/method.md
      '../../' — nested structure (office-api): ClassName/Methods/method.md

    example_editor_name is appended to the ```javascript fence, e.g. 'editor-docx'.
    """
    method_name = method['name']
    description = correct_description(method.get('description', 'No description provided.'), root)
    params = method.get('params', [])
    returns = method.get('returns', [])
    memberof = method.get('memberof', '')

    content = f"# {method_name}\n\n{description}"

    # Syntax
    param_list = ', '.join([p['name'] for p in params if '.' not in p['name']]) if params else ''
    content += f"\n\n## {get_translation('Syntax')}\n\n```javascript\nexpression.{method_name}({param_list});\n```"
    if memberof:
        # Flat structure (plugins, root='../'): class summary is Methods.md in Methods/ folder.
        # Nested structure (office-api, root='../../'): class page is ../{memberof}.md.
        memberof_url = 'Methods.md' if root.count('../') == 1 else f'../{memberof}.md'
        content += f"\n\n`expression` - {get_translation(f'A variable that represents a [{memberof}]({memberof_url}) class.')}"

    # Parameters
    content += f"\n\n## {get_translation('Parameters')}\n\n"
    if params:
        content += f"| **{get_translation('Name')}** | **{get_translation('Required/Optional')}** | **{get_translation('Data type')}** | **{get_translation('Default')}** | **{get_translation('Description')}** |\n"
        content += "| ------------- | ------------- | ------------- | ------------- | ------------- |"
        for param in params:
            param_name = param.get('name', 'Unnamed')
            param_types = param.get('type', {}).get('names', []) if param.get('type') else []
            param_types_md = generate_data_types_markdown(param_types, enumerations, classes, root)
            param_desc = correct_description(param.get('description', 'No description provided.'), root, True)
            param_required = get_translation('Required') if not param.get('optional') else get_translation('Optional')
            param_default = correct_default_value(param.get('defaultvalue', ''), enumerations, classes, root)
            content += f"\n| {param_name} | {param_required} | {param_types_md} | {param_default} | {param_desc} |"
    else:
        content += get_translation("This method doesn't have any parameters.")

    # Returns
    content += f"\n\n## {get_translation('Returns')}\n\n"
    if returns:
        return_type_list = returns[0].get('type', {}).get('names', [])
        content += generate_data_types_markdown(return_type_list, enumerations, classes, root)
    else:
        content += get_translation("This method doesn't return any data.")

    content += generate_example_markdown(method.get('example', ''), example_editor_name)

    return escape_text_outside_code_blocks(content)

def generate_example_markdown(example, example_editor_name=''):
    if example:
        comment, code = example.split('```js', 1)
        comment = get_translation(comment.strip())
        code = code.strip().strip('`').strip()
        return f"\n\n## {get_translation('Example')}\n\n{comment}{'\n\n' if comment else ''}```javascript{" " if example_editor_name else ""}{example_editor_name}\n{code}\n```\n\n"
    return '\n\n'
