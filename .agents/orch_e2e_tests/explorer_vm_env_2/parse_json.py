import json

with open(r'c:\Work\.agents\orch_e2e_tests\explorer_vm_env_2\vm_investigation_complete.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== SYSTEM INFO ===")
print(json.dumps(data['system'], indent=2))

print("\n=== TARGETED PACKAGES ===")
print(json.dumps(data['targeted_packages'], indent=2))

print("\n=== DIRECTORIES SUMMARY ===")
for d, info in data['dirs'].items():
    print(f"\n--- {d} ---")
    print(f"Exists: {info.get('exists')}, Mode: {info.get('mode')}")
    if 'children' in info:
        print("Children:")
        for c in info['children']:
            print(f"  {c['name']} (dir={c['is_dir']}, size={c['size']}, mode={c['mode']})")

print("\n=== TRANSLATION KIOSK DETAILS ===")
print(json.dumps(data['translation_kiosk_details'], indent=2))

print(f"\n=== AUDIO SUMMARY: {data['total_audio_files_found']} total files across {len(data['audio_languages_summary'])} folders ===")
for folder, summary in sorted(data['audio_languages_summary'].items()):
    print(f"\nFolder: {folder}")
    print(f"  Count: {summary['count']}")
    print(f"  Sample Rates: {summary['sample_rates']}")
    print(f"  Channels: {summary['channels']}")
    print(f"  Total Duration: {summary['total_duration_sec']}s (~{summary['total_duration_sec']/60:.1f} mins)")
    print(f"  Files sample:")
    for file_info in summary['files'][:5]:
        print(f"    - {file_info['filename']}: {file_info['duration_sec']}s, {file_info['sample_rate']}Hz, {file_info['channels']}ch, {file_info['size_bytes']} bytes")
    if len(summary['files']) > 5:
        print(f"    ... and {len(summary['files']) - 5} more files")
