# Navigate to the project directory
Set-Location -Path "D:\Projects\Python\TNFCDataInjector_v2\"

# Activate the virtual environment
& "D:\Projects\Python\TNFCDataInjector_v2\.venv\Scripts\Activate.ps1"

# Run the Python script
python Main.py

# Pause the console (like pause in batch)
Read-Host -Prompt "Press Enter to exit"
