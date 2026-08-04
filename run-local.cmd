@echo off
REM Double-click / one-command launcher for the Team105 dataset wizard (SPEC-004).
REM Runs scripts\run-local.ps1 with the execution policy bypassed for this
REM process only (does not change machine/user policy). Forwards any flags,
REM e.g.  run-local.cmd -Share   or   run-local.cmd -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-local.ps1" %*
