@echo off
cd /d C:\Users\Sohei\dev\whisper-transcription
call "C:\Users\Sohei\anaconda3\Scripts\activate.bat" "C:\Users\Sohei\anaconda3"
call conda activate whisper-transcription
python gui.py
pause
