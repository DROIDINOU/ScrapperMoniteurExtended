import os

root = "staticfiles"
for dirpath, dirnames, filenames in os.walk(root):
    for f in filenames:
        print("📦", os.path.join(dirpath, f))