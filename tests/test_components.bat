@echo off
cd "c:\Users\Jason\Desktop\UmukoziHR\umukozihr-tailor\server"
call venv\Scripts\activate.bat
python tests\test_components.py
pause