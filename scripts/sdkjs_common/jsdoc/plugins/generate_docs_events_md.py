#!/usr/bin/env python3
import os
import json
import shutil
import argparse
import sys
import generate_docs_events_json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
import generate_docs_md_common as common
from generate_docs_md_common import (
    load_json, write_markdown_file, get_translation,
    generate_example_markdown,
    correct_description, escape_text_outside_code_blocks,
    generate_data_types_markdown, generate_enumeration_markdown,
)

# Папки для каждого editor_name
editors = {
    "word": "text-document-api",
    "cell": "spreadsheet-api",
    "slide": "presentation-api",
    "forms": "form-api",
    "pdf": "pdf-api"
}

script_path = os.path.abspath(__file__)
root = os.path.abspath(os.path.join(os.path.dirname(script_path), '../../../../..'))

# ─── Event-specific generators ────────────────────────────────────────────────

def generate_event_markdown(event, enumerations):
    name = event['name']
    desc = correct_description(event.get('description', ''), '../', True, enum_file_prefix='Event_')
    params = event.get('params', [])

    md = f"# {name}\n\n{desc}"

    md += f"\n\n## {get_translation('Parameters')}\n\n"
    if params:
        md += f"| **{get_translation('Name')}** | **{get_translation('Data type')}** | **{get_translation('Description')}** |\n"
        md += "| --------- | ------------- | ----------- |"
        for p in params:
            t_md = generate_data_types_markdown(
                p.get('type', {}).get('names', []),
                enumerations, {}, enum_file_prefix='Event_'
            )
            d = correct_description(p.get('description', ''), isInTable=True, enum_file_prefix='Event_')
            md += f"\n| {p['name']} | {t_md} | {d} |"
    else:
        md += f"{get_translation('This event has no parameters.')}"

    md += generate_example_markdown(event.get('example', ''))

    return escape_text_outside_code_blocks(md)

def generate_events_summary(events):
    header = [
        f"# {get_translation('Events')}\n\n",
        f"| {get_translation('Event')} | {get_translation('Description')} |\n",
        "| ----- | ----------- |\n"
    ]
    lines = [
        f"| [{ev['name']}](./{ev['name']}.md) | "
        f"{correct_description(ev.get('description', ''), '../', isInTable=True, enum_file_prefix='Event_')} |\n"
        for ev in sorted(events, key=lambda e: e['name'])
    ]
    return "".join(header + lines)

# ─── Cleanup helpers ──────────────────────────────────────────────────────────

def clean_editor_dir(editor_dir):
    for root_dir, dirs, files in os.walk(editor_dir, topdown=False):
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
            if file.startswith('Event_') and not file.endswith('.json'):
                os.remove(os.path.join(root_dir, file))

# ─── Processing ───────────────────────────────────────────────────────────────

def process_events(data, editor_dir):
    enumerations = []
    events = []

    for doclet in data:
        kind = doclet.get('kind')
        if kind == 'typedef':
            enumerations.append(doclet)
        elif kind == 'event':
            events.append(doclet)

    events_dir = f'{editor_dir}/Events'
    clean_editor_dir(events_dir)
    os.makedirs(events_dir, exist_ok=True)
    common.used_enumerations.clear()

    for ev in events:
        path = os.path.join(events_dir, f"{ev['name']}.md")
        write_markdown_file(path, generate_event_markdown(ev, enumerations))
        if not ev.get('example'):
            common.missing_examples.append(os.path.relpath(path, events_dir))

    enum_dir = os.path.join(editor_dir, 'Enumeration')
    clean_enum_files(enum_dir)
    os.makedirs(enum_dir, exist_ok=True)

    prev = -1
    while len(common.used_enumerations) != prev:
        prev = len(common.used_enumerations)
        for e in enumerations:
            if e['name'] in common.used_enumerations:
                generate_enumeration_markdown(e, enumerations, {}, enum_file_prefix='Event_')

    for e in enumerations:
        if e['name'] in common.used_enumerations:
            path = os.path.join(enum_dir, f"Event_{e['name']}.md")
            write_markdown_file(path, generate_enumeration_markdown(e, enumerations, {}, enum_file_prefix='Event_'))
            if not e.get('example'):
                common.missing_examples.append(os.path.relpath(path, editor_dir))

    write_markdown_file(os.path.join(events_dir, "Events.md"), generate_events_summary(events))

def generate_events(output_dir, translations_file):
    if translations_file is not None and os.path.exists(translations_file):
        common.translations = load_json(translations_file)
        common.translations_lang = os.path.splitext(os.path.basename(translations_file))[0]
    else:
        common.translations = {}

    os.chdir(os.path.dirname(script_path))

    if output_dir.endswith('/'):
        output_dir = output_dir[:-1]
    tmp = os.path.join(output_dir, 'tmp_json')

    generate_docs_events_json.generate(tmp, md=True)

    for editor_name, folder in editors.items():
        data = load_json(os.path.join(tmp, f"{editor_name}.json"))
        process_events(data, os.path.join(output_dir, folder))

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

    shutil.rmtree(tmp)
    print("Done. Missing examples:", common.missing_examples)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate events documentation")
    parser.add_argument(
        "destination",
        nargs="?",
        default=f"{root}/api.onlyoffice.com/site/docs/plugin-and-macros/interacting-with-editors/",
        help="Output directory"
    )
    parser.add_argument(
        "--translations",
        type=str,
        help="Path to the JSON file with translations",
        nargs='?',
        default=None
    )

    args = parser.parse_args()

    generate_events(args.destination, args.translations)
