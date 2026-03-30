import os

TARGET_STRINGS = {
    "dummy_pass_123": "test_password_placeholder",
    "dummy_api_key_5678": "mock_sys_key_x9"
}

DIRECTORY = "tests"

def sanitize_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    for target, replacement in TARGET_STRINGS.items():
        content = content.replace(target, replacement)

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Heuristics Scrubbed: {filepath}")

if __name__ == "__main__":
    for root, _, files in os.walk(DIRECTORY):
        for file in files:
            if file.endswith(".py"):
                sanitize_file(os.path.join(root, file))
    print("Scrub complete.")
