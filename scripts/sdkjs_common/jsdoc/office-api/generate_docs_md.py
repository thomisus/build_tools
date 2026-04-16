import os
import json
import shutil
import argparse
import sys
import generate_docs_json

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
    "pdf": "pdf-api",
}

script_path = os.path.abspath(__file__)
root = os.path.abspath(os.path.join(os.path.dirname(script_path), '../../../../..'))


def process_doclets(data, output_dir, editor_name):
    common.cur_editor_name = editor_name

    classes = {}
    classes_props = {}
    classes_augments = {}
    enumerations = []
    editor_dir = os.path.join(output_dir, editors[editor_name])
    example_editor_name = 'editor-'

    if editor_name == 'word':
        example_editor_name += 'docx'
    elif editor_name == 'forms':
        example_editor_name += 'forms'
    elif editor_name == 'slide':
        example_editor_name += 'pptx'
    elif editor_name == 'cell':
        example_editor_name += 'xlsx'
    elif editor_name == 'pdf':
        example_editor_name += 'pdf'

    for doclet in data:
        if doclet['kind'] == 'class':
            class_name = doclet['name']
            if class_name:
                if class_name not in classes:
                    classes[class_name] = []
                classes_props[class_name] = doclet.get('properties', None)
                classes_augments[class_name] = doclet.get('augments', None)
        elif doclet['kind'] == 'function':
            class_name = doclet.get('memberof')
            if class_name:
                if class_name not in classes:
                    classes[class_name] = []
                classes[class_name].append(doclet)
        elif doclet['kind'] == 'typedef':
            enumerations.append(doclet)

    # Process classes
    for class_name, methods in classes.items():
        if len(methods) == 0:
            continue

        class_dir = os.path.join(editor_dir, class_name)
        methods_dir = os.path.join(class_dir, 'Methods')
        os.makedirs(methods_dir, exist_ok=True)

        class_content = generate_class_markdown(
            class_name,
            methods,
            classes_props[class_name],
            enumerations,
            classes,
            augments=classes_augments.get(class_name),
            path_to_methods='./Methods/',
        )
        write_markdown_file(os.path.join(class_dir, f"{class_name}.md"), class_content)

        for method in methods:
            method_file_path = os.path.join(methods_dir, f"{method['name']}.md")
            method_content = generate_method_markdown(method, enumerations, classes, root='../../', example_editor_name=example_editor_name)
            write_markdown_file(method_file_path, method_content)

            if not method.get('example', ''):
                common.missing_examples.append(os.path.relpath(method_file_path, output_dir))

    # Process enumerations
    enum_dir = os.path.join(editor_dir, 'Enumeration')
    os.makedirs(enum_dir, exist_ok=True)

    prev_used_count = -1
    while len(common.used_enumerations) != prev_used_count:
        prev_used_count = len(common.used_enumerations)
        for enum in [e for e in enumerations if e['name'] in common.used_enumerations]:
            generate_enumeration_markdown(enum, enumerations, classes, example_editor_name)

    for enum in enumerations:
        enum_file_path = os.path.join(enum_dir, f"{enum['name']}.md")
        enum_content = generate_enumeration_markdown(enum, enumerations, classes, example_editor_name)
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

    generate_docs_json.generate(output_dir + 'tmp_json', md=True)
    for editor_name, folder_name in editors.items():
        input_file = os.path.join(output_dir + '/tmp_json', editor_name + ".json")

        editor_folder_path = os.path.join(output_dir, folder_name)
        for item in os.listdir(editor_folder_path):
            item_path = os.path.join(editor_folder_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)

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

    shutil.rmtree(output_dir + 'tmp_json')
    print('Done')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate documentation")
    parser.add_argument(
        "destination",
        type=str,
        help="Destination directory for the generated documentation",
        nargs='?',
        default=f"{root}/api.onlyoffice.com/site/docs/office-api/usage-api/"
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
