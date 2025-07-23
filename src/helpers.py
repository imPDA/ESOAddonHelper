import os
from pprint import pprint
import re
from typing import Dict, List, Optional, Union

import ctypes.wintypes
import pathlib
from typing import Literal
CSIDL_PERSONAL = 5
SHGFP_TYPE_CURRENT = 0 


def get_addons_folder_windows(version: Literal['live', 'pts']):
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)

    addons_folder = pathlib.Path(buf.value).resolve() / f'Elder Scrolls Online/{version}/AddOns'

    return addons_folder


def extract_all_addons_data(addons_path: str) -> List[Dict[str, Union[str, bool]]]:
    addons = []
    
    if not os.path.exists(addons_path):
        print('path does not exists')
        return addons
    
    for root_path, dirs, files in os.walk(addons_path):
        root_path = pathlib.Path(root_path).resolve()

        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if not (file.endswith('.txt') or file.endswith('.addon')):
                continue
                
            manifest_path = os.path.join(root_path, file)
            
            try:
                with open(manifest_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
            except UnicodeDecodeError:
                continue
    
            manifest_filename = os.path.splitext(file)[0]

            if '## Title' not in content:
                print(file, 'is not a manifest')
                continue

            addon = {
                'manifest_filename': manifest_filename,
                'manifest_path': manifest_path,
                'root_path': root_path,
                'relative_path': os.path.relpath(root_path, addons_path),  # ?
                'bundled': root_path.parent != addons_path,
                'errors': [],
            }
            addons.append(addon)

            lines = content.split('\n')

            for line in lines:
                if line.startswith(';'):
                    continue

                if line.startswith('##'):
                    handle_metadata_line(addon, line)

    for addon in addons:
        run_checks(addon)
                
    return addons


METADATA_FIELDS = {
    'Title': lambda x: {'title': clean_colors(x)},
    'Version': lambda x: {'version': x},
    'Description': lambda x: {'description': x},
    'APIVersion': lambda x: {'api': list(map(int, x.split()))},
    'Author': lambda x: {'author': clean_colors(x)},
    'AddOnVersion': lambda x: {'addonVersion': x},
    'AddonVersion': lambda x: {'addonVersion': x},
    'DependsOn': lambda x: {'dependsOn': x.split()},
    'PCDependsOn': lambda x: {'pcDependsOn': x.split()},
    'ConsoleDependsOn': lambda x: {'consoleDependsOn': x.split()},
    'OptionalDependsOn': lambda x: {'optionalDependsOn': x.split()},
    'SavedVariables': lambda x: {'savedVariables': x.split()},
    'IsLibrary': lambda x: {'isLibrary': x == 'true'},
    'IntVersion': lambda x: {'intVersion': int(x)},
}


def handle_metadata_line(addon_data: dict, line: str) -> None:
    match = re.match(r'^\s*##\s*(\w*):\s*(.*)', line)
    if not match:
        addon_data['errors'].append(f'Bad format for metadata line: {line}')
        return

    groups = match.groups()

    metadata_field_name = groups[0]
    metadata_value = groups[1]
    
    if metadata_field_name not in METADATA_FIELDS:
        addon_data['errors'].append(f'Unknown metadata field `{metadata_field_name}`: {line}')
        return

    addon_data.update(METADATA_FIELDS[metadata_field_name](metadata_value))


def clean_colors(text: Optional[str]) -> Optional[str]:
    if not text:
        return text

    return re.sub(r'\|c[0-9a-fA-F]{6}(.*?)\|r', r'\1', text)


def folderNameMatchesManifest(addon_data):
    matches = addon_data['manifest_filename'] == addon_data['root_path'].name

    if not matches:
        print(f"`{addon_data['title']}` from `{addon_data['relative_path']}` will not be loaded: Manifest name mismatch")

    return matches


CHECKS = {
    folderNameMatchesManifest,
}

def run_checks(addon_data):
    addon_data['ok'] = all(check(addon_data) for check in CHECKS)


if __name__ == '__main__':
    folder_live = get_addons_folder_windows('live')
    folder_pts = get_addons_folder_windows('pts')
    
    addons_data = extract_all_addons_data(folder_live)
    pprint(addons_data)
    print(len(addons_data))
