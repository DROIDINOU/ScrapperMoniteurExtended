import os
import psutil

# Cœurs logiques (threads visibles par l'OS)
logical_cores = os.cpu_count()

# Cœurs physiques (vrais cœurs hardware)
physical_cores = psutil.cpu_count(logical=False)

print(f"Cœurs logiques (threads) : {logical_cores}")
print(f"Cœurs physiques         : {physical_cores}")
