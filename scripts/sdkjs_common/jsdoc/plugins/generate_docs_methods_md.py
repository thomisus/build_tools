import os
import json
import shutil
import argparse
import sys
import generate_docs_methods_json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
import generate_docs_md_common as common
from generate_docs_md_common import (
    load_json, write_markdown_file,
    generate_class_markdown, generate_method_markdown, generate_enumeration_markdown,
)

# Configuration files
editors = {
    "word": "text-document-api",
    "cell": "spreadsheet-api",
    "slide": "presentation-api",
    "forms": "form-api",
    "pdf": "pdf-api"
}

script_path = os.path.abspath(__file__)
root = os.path.abspath(os.path.join(os.path.dirname(script_path), '../../../../..'))


def clean_methods_dir(methods_dir):
    for root_dir, dirs, files in os.walk(methods_dir, topdown=False):
        for file in files:
            if not file.endswith('.json'):
                os.remove(os.path.join(root_dir, file))
        for dir in dirs:
            dir_path = os.path.join(root_dir, dir)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)

def clean_enum_files(editor_dir: str):
    for root_dir, _, files in os.walk(editor_dir, topdown=False):
        for file in files:
            if not file.startswith('Event_') and not file.endswith('.json'):
                os.remove(os.path.join(root_dir, file))

def process_doclets(data, output_dir, editor_name):
    common.cur_editor_name = editor_name

    classes = {}
    classes_props = {}
    enumerations = []
    editor_dir = os.path.join(output_dir, editors[editor_name])
    methods_dir = os.path.join(output_dir, editors[editor_name], 'Methods')

    clean_methods_dir(methods_dir)
    os.makedirs(methods_dir, exist_ok=True)

    for doclet in data:
        if doclet['kind'] == 'class':
            class_name = doclet['name']
            if class_name:
                if class_name not in classes:
                    classes[class_name] = []
                classes_props[class_name] = doclet.get('properties', None)
        elif doclet['kind'] == 'function':
            class_name = doclet.get('memberof')
            if class_name:
                if class_name not in classes:
                    classes[class_name] = []
                classes[class_name].append(doclet)
        elif doclet['kind'] == 'typedef':
            enumerations.append(doclet)

    # Process api methods
    class_name = 'Api'
    methods = classes[class_name]
    class_content = generate_class_markdown(
        class_name,
        methods,
        classes_props[class_name],
        enumerations,
        classes
    )
    write_markdown_file(os.path.join(methods_dir, "Methods.md"), class_content)

    for method in methods:
        method_file_path = os.path.join(methods_dir, f"{method['name']}.md")
        method_content = generate_method_markdown(method, enumerations, classes)
        write_markdown_file(method_file_path, method_content)

        if not method.get('example', ''):
            common.missing_examples.append(os.path.relpath(method_file_path, output_dir))

    # Process enumerations
    enum_dir = os.path.join(editor_dir, 'Enumeration')
    clean_enum_files(enum_dir)
    os.makedirs(enum_dir, exist_ok=True)

    prev_used_count = -1
    while len(common.used_enumerations) != prev_used_count:
        prev_used_count = len(common.used_enumerations)
        for enum in [e for e in enumerations if e['name'] in common.used_enumerations]:
            generate_enumeration_markdown(enum, enumerations, classes)

    for enum in enumerations:
        enum_file_path = os.path.join(enum_dir, f"{enum['name']}.md")
        enum_content = generate_enumeration_markdown(enum, enumerations, classes)
        if enum_content is None:
            continue

        write_markdown_file(enum_file_path, enum_content)
        if not enum.get('example', ''):
            common.missing_examples.append(os.path.relpath(enum_file_path, output_dir))

def generate(output_dir, translations_file):
    common.global_output_dir = output_dir

    if translations_file is not None and os.path.exists(translations_file):
        common.translations = load_json(translations_file)
        common.translations_lang = os.path.splitext(os.path.basename(translations_file))[0]
    else:
        common.translations = {}

    os.chdir(os.path.dirname(script_path))

    print('Generating Markdown documentation...')

    if output_dir[-1] == '/':
        output_dir = output_dir[:-1]

    generate_docs_methods_json.generate(output_dir + '/tmp_json', md=True)
    for editor_name, folder_name in editors.items():
        input_file = os.path.join(output_dir + '/tmp_json', editor_name + ".json")

        data = load_json(input_file)
        common.used_enumerations.clear()
        process_doclets(data, output_dir, editor_name)

    if translations_file is not None:
        target_dir = os.path.dirname(translations_file)

        missed_file_path = os.path.join(target_dir, "missed_translations.json")
        print(f'Saving missed translations to: {missed_file_path}')
        with open(missed_file_path, 'w', encoding='utf-8') as f:
            json.dump(common.missed_translations, f, ensure_ascii=False, indent=4)

        unused_keys = set(common.translations.keys()) - set(common.used_translations_keys.keys())
        unused_data = {k: common.translations[k] for k in unused_keys}
        unused_file_path = os.path.join(target_dir, "unused_translations.json")
        print(f'Saving unused translations to: {unused_file_path}')
        with open(unused_file_path, 'w', encoding='utf-8') as f:
            json.dump(unused_data, f, ensure_ascii=False, indent=4)

    shutil.rmtree(output_dir + '/tmp_json')
    print('Done')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate documentation")
    parser.add_argument(
        "destination",
        type=str,
        help="Destination directory for the generated documentation",
        nargs='?',
        default=f"{root}/api.onlyoffice.com/site/docs/plugin-and-macros/interacting-with-editors/"
    )
    parser.add_argument(
        "--translations",
        type=str,
        help="Path to the JSON file with translations",
        nargs='?',
        default=None
    )

    args = parser.parse_args()

    generate(args.destination, args.translations)
    print("START_MISSING_EXAMPLES")
    print(",".join(common.missing_examples))
    print("END_MISSING_EXAMPLES")
