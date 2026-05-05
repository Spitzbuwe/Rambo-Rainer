@echo off
cd /d "%~dp0"
start "" python backend\main.py
cd frontend
npm run dev
