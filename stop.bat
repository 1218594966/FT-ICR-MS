@echo off
chcp 65001 >nul
echo 正在停止 FT-ICR MS 服务...
taskkill /FI "WindowTitle eq FTICRMS-Backend*" /F 2>nul
taskkill /FI "WindowTitle eq FTICRMS-Frontend*" /F 2>nul
echo 服务已停止。
