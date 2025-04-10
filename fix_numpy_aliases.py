import os

import re



# Root of the repo

repo_root = "/projects/elhe2720/software/multiviewtracks"



# Aliases to fix

alias_map = {

    r"np\.int\b": "int",

    r"np\.float\b": "float",

    r"np\.bool\b": "bool",

    r"np\.object\b": "object",

    r"np\.str\b": "str",

    r"np\.long\b": "int",  # long doesn't exist in Python 3

}



def patch_file(filepath):

    with open(filepath, "r") as f:

        content = f.read()



    original = content

    for pattern, replacement in alias_map.items():

        content = re.sub(pattern, replacement, content)



    if content != original:

        print(f"🛠️  Patched: {filepath}")

        with open(filepath, "w") as f:

            f.write(content)



# Walk through the repo

for root, _, files in os.walk(repo_root):

    for file in files:

        if file.endswith(".py"):

            patch_file(os.path.join(root, file))


