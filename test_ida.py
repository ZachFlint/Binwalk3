import sys
import os
sys.path.insert(0, r'D:\Binwalk3')
import binwalk

file_path = r"C:\Program Files\IDA Professional 9.1\ida.exe"

print("="*80)
print(f"Scanning: {file_path}")
print("="*80)

results = binwalk.scan(file_path)

for module in results:
    print(f"\nFile Size: {os.path.getsize(file_path):,} bytes")
    print(f"Signatures Found: {len(module.results)}")
    print(f"Errors: {len(module.errors)}\n")

    if len(module.errors) > 0:
        print("ERRORS:")
        for err in module.errors:
            print(f"  - {err}")
        print()

    if len(module.results) == 0:
        print("No signatures detected")
    else:
        for idx, result in enumerate(module.results, 1):
            print(f"[{idx}] Offset: 0x{result.offset:X} ({result.offset} bytes)")
            print(f"    Description: {result.description}")
            if result.size:
                print(f"    Size: {result.size} bytes")
            print(f"    Module: {result.module}")
            print()
