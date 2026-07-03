@echo off
chcp 65001>nul
cd /d C:\ov_models
set HF_ENDPOINT=https://hf-mirror.com
set no_proxy=*
python C:\ov_models\asr_service.py >> C:\ov_models\asr.log 2>&1
