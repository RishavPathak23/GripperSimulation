:: SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
:: SPDX-License-Identifier: Apache-2.0
::
:: Licensed under the Apache License, Version 2.0 (the "License");
:: you may not use this file except in compliance with the License.
:: You may obtain a copy of the License at
::
:: http://www.apache.org/licenses/LICENSE-2.0
::
:: Unless required by applicable law or agreed to in writing, software
:: distributed under the License is distributed on an "AS IS" BASIS,
:: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
:: See the License for the specific language governing permissions and
:: limitations under the License.

@echo off
setlocal

:: Check if Long Paths are enabled in Windows Registry
:: Registry path: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem
:: Value name: LongPathsEnabled

echo Checking Windows Long Paths support...

:: Query the registry value using reg query
reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo WARNING: LongPathsEnabled registry value not found.
    echo Long file paths may not be supported on this system.
    echo This may result in build errors related to missing files.
    echo.
    echo To enable long paths support:
    echo 1. Run PowerShell as Administrator
    echo 2. Execute: New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
    echo 3. Restart your system
    echo.
    echo Continuing build anyway...
    exit /b 0
)

:: Get the actual value
for /f "tokens=3" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled ^| find "LongPathsEnabled"') do (
    set LONGPATH_VALUE=%%a
)

if "%LONGPATH_VALUE%"=="0x1" (
    echo Long Paths support is enabled.
    exit /b 0
) else if "%LONGPATH_VALUE%"=="0x0" (
    echo.
    echo WARNING: Long Paths support is DISABLED.
    echo Current value: LongPathsEnabled = 0
    echo.
    echo Long file paths may cause build issues. 
    echo This may result in build errors related to missing files.
    echo To enable long file paths support:
    echo 1. Run PowerShell as Administrator
    echo 2. Execute: Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1
    echo 3. Restart your system
    echo.
    echo Continuing build anyway...
    exit /b 0
) else (
    echo WARNING: Unexpected LongPathsEnabled value: %LONGPATH_VALUE%
    echo Continuing build anyway...
    exit /b 0
)

endlocal

