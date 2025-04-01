# scripts/reorganize_cogs.py
import os
import shutil

# Define the new structure
structure = {
    "moderation": ["automod.py", "moderation.py"],
    "utilities": ["devlogger.py", "help.py", "logs.py", "owner.py"],
    "entertainment": ["games.py", "interactions.py", "reaction.py"],
    "features/confessions": ["confessions.py", "anonconf_deleter.py"]
}

# Create directories and __init__.py files
os.makedirs("cogs/common", exist_ok=True)
with open("cogs/__init__.py", "w") as f:
    f.write("# This file makes the directory a Python package\n")

with open("cogs/common/__init__.py", "w") as f:
    f.write("# Common utilities for all cogs\n")

# Create category directories
for category in structure:
    os.makedirs(f"cogs/{category}", exist_ok=True)
    with open(f"cogs/{category}/__init__.py", "w") as f:
        f.write(f"# {category.capitalize()} cogs\n")

# Copy files to their new locations
for category, files in structure.items():
    for file in files:
        source = f"cogs/{file}"
        destination = f"cogs/{category}/{file}"
        if os.path.exists(source):
            shutil.copy2(source, destination)
            print(f"Copied {source} to {destination}")
        else:
            print(f"Warning: Source file {source} not found")

print("Reorganization complete!")