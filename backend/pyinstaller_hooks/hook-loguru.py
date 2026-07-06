"""
PyInstaller hook for loguru.
Ensures loguru's internals are properly collected.
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all loguru submodules
hiddenimports = collect_submodules('loguru')

# Collect any data files loguru might need
datas = collect_data_files('loguru')