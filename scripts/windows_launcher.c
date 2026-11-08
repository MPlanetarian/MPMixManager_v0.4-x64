/*
 * MP_Mix_Manager - Native 64-bit Windows Launcher
 * Automatically locates Git Bash, MSYS2, or WSL, enables VT100 / ANSI escape sequences,
 * and launches Mix_Archive_Manager.sh directly with forward arguments.
 */

#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

#ifndef ENABLE_VIRTUAL_TERMINAL_PROCESSING
#define ENABLE_VIRTUAL_TERMINAL_PROCESSING 0x0004
#endif

/* Enable Windows 10/11 native ANSI/VT100 color rendering in console */
static void enable_ansi_virtual_terminal(void) {
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut != INVALID_HANDLE_VALUE && hOut != NULL) {
        DWORD dwMode = 0;
        if (GetConsoleMode(hOut, &dwMode)) {
            dwMode |= ENABLE_VIRTUAL_TERMINAL_PROCESSING;
            SetConsoleMode(hOut, dwMode);
        }
    }
}

static BOOL file_exists(const wchar_t *path) {
    if (!path || !*path) return FALSE;
    DWORD attr = GetFileAttributesW(path);
    return (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY));
}

int wmain(int argc, wchar_t *argv[]) {
    enable_ansi_virtual_terminal();

    /* Set UTF-8 encoding environment variable for Python and shell child processes */
    SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8");

    /* 1. Determine application root directory from executable path */
    wchar_t appDir[MAX_PATH * 2] = {0};
    DWORD len = GetModuleFileNameW(NULL, appDir, MAX_PATH * 2);
    if (len == 0 || len >= MAX_PATH * 2) {
        wprintf(L"[ERROR] Failed to determine application directory.\n");
        return 1;
    }
    wchar_t *lastSlash = wcsrchr(appDir, L'\\');
    if (lastSlash) {
        *lastSlash = L'\0';
    } else {
        wcscpy(appDir, L".");
    }

    SetCurrentDirectoryW(appDir);

    /* 2. Locate Mix_Archive_Manager.sh */
    wchar_t scriptPath[MAX_PATH * 2] = {0};
    _snwprintf(scriptPath, MAX_PATH * 2, L"%s\\Mix_Archive_Manager.sh", appDir);
    if (!file_exists(scriptPath)) {
        wprintf(L"==============================================================================\n");
        wprintf(L"[ERROR] Mix_Archive_Manager.sh was not found in:\n  %s\n", appDir);
        wprintf(L"==============================================================================\n");
        wprintf(L"Press [Enter] to exit...\n");
        (void)getchar();
        return 1;
    }

    /* 3. Convert script directory to Unix forward-slash path for Bash */
    wchar_t unixScript[MAX_PATH * 2] = {0};
    wcscpy(unixScript, scriptPath);
    for (wchar_t *p = unixScript; *p; p++) {
        if (*p == L'\\') *p = L'/';
    }

    /* 4. Find bash.exe */
    wchar_t bashPath[MAX_PATH * 2] = {0};
    const wchar_t *knownPaths[] = {
        L"C:\\Program Files\\Git\\bin\\bash.exe",
        L"C:\\Program Files (x86)\\Git\\bin\\bash.exe",
        L"C:\\msys64\\usr\\bin\\bash.exe",
        L"C:\\msys64\\bin\\bash.exe",
        NULL
    };

    /* Check known standard locations */
    for (int i = 0; knownPaths[i] != NULL; i++) {
        if (file_exists(knownPaths[i])) {
            wcscpy(bashPath, knownPaths[i]);
            break;
        }
    }

    /* Check %LOCALAPPDATA%\Programs\Git\bin\bash.exe */
    if (!bashPath[0]) {
        wchar_t localApp[MAX_PATH] = {0};
        if (GetEnvironmentVariableW(L"LOCALAPPDATA", localApp, MAX_PATH) > 0) {
            wchar_t cand[MAX_PATH * 2];
            _snwprintf(cand, MAX_PATH * 2, L"%s\\Programs\\Git\\bin\\bash.exe", localApp);
            if (file_exists(cand)) {
                wcscpy(bashPath, cand);
            }
        }
    }

    /* Check %ProgramFiles%\Git\bin\bash.exe dynamically */
    if (!bashPath[0]) {
        wchar_t progFiles[MAX_PATH] = {0};
        if (GetEnvironmentVariableW(L"ProgramFiles", progFiles, MAX_PATH) > 0) {
            wchar_t cand[MAX_PATH * 2];
            _snwprintf(cand, MAX_PATH * 2, L"%s\\Git\\bin\\bash.exe", progFiles);
            if (file_exists(cand)) {
                wcscpy(bashPath, cand);
            }
        }
    }

    /* Check in PATH via SearchPathW (ignoring WindowsApps stubs) */
    if (!bashPath[0]) {
        wchar_t found[MAX_PATH * 2] = {0};
        if (SearchPathW(NULL, L"bash.exe", NULL, MAX_PATH * 2, found, NULL) > 0) {
            if (wcsstr(found, L"WindowsApps") == NULL && file_exists(found)) {
                wcscpy(bashPath, found);
            }
        }
    }

    /* 5. Assemble command-line arguments */
    wchar_t *cmdLineArgs = GetCommandLineW();
    /* Advance past executable name */
    if (cmdLineArgs) {
        if (*cmdLineArgs == L'\"') {
            cmdLineArgs++;
            while (*cmdLineArgs && *cmdLineArgs != L'\"') cmdLineArgs++;
            if (*cmdLineArgs == L'\"') cmdLineArgs++;
        } else {
            while (*cmdLineArgs && *cmdLineArgs != L' ' && *cmdLineArgs != L'\t') cmdLineArgs++;
        }
        while (*cmdLineArgs == L' ' || *cmdLineArgs == L'\t') cmdLineArgs++;
    } else {
        cmdLineArgs = L"";
    }

    wchar_t fullCommand[MAX_PATH * 8] = {0};

    if (bashPath[0]) {
        if (*cmdLineArgs) {
            _snwprintf(fullCommand, MAX_PATH * 8, L"\"%s\" \"%s\" %s", bashPath, unixScript, cmdLineArgs);
        } else {
            _snwprintf(fullCommand, MAX_PATH * 8, L"\"%s\" \"%s\"", bashPath, unixScript);
        }
    } else {
        /* Check for WSL */
        wchar_t wslPath[MAX_PATH] = {0};
        if (SearchPathW(NULL, L"wsl.exe", NULL, MAX_PATH, wslPath, NULL) > 0) {
            if (*cmdLineArgs) {
                _snwprintf(fullCommand, MAX_PATH * 8, L"wsl.exe bash -c \"cd '$(wslpath -a '%s')' && ./Mix_Archive_Manager.sh %s\"", unixScript, cmdLineArgs);
            } else {
                _snwprintf(fullCommand, MAX_PATH * 8, L"wsl.exe bash -c \"cd '$(wslpath -a '%s')' && ./Mix_Archive_Manager.sh\"", unixScript);
            }
        } else {
            /* Fallback to manager.ps1 or manager.bat if present */
            wchar_t ps1Path[MAX_PATH * 2] = {0};
            _snwprintf(ps1Path, MAX_PATH * 2, L"%s\\manager.ps1", appDir);
            if (file_exists(ps1Path)) {
                _snwprintf(fullCommand, MAX_PATH * 8, L"powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"%s\" %s", ps1Path, cmdLineArgs);
            } else {
                wprintf(L"==============================================================================\n");
                wprintf(L"  MP MIX ARCHIVE MANAGER - 64-BIT WINDOWS LAUNCHER                            \n");
                wprintf(L"==============================================================================\n");
                wprintf(L"[ERROR] No compatible Bash or WSL2 environment was detected!\n\n");
                wprintf(L"Please install Git for Windows (recommended) from:\n");
                wprintf(L"  https://git-scm.com/download/win\n\n");
                wprintf(L"Or enable Windows Subsystem for Linux (WSL2):\n");
                wprintf(L"  wsl --install\n");
                wprintf(L"==============================================================================\n");
                wprintf(L"Press [Enter] to exit...\n");
                (void)getchar();
                return 1;
            }
        }
    }

    /* 6. Launch child process inheriting console standard handles */
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    BOOL success = CreateProcessW(
        NULL,
        fullCommand,
        NULL,
        NULL,
        TRUE,
        0,
        NULL,
        appDir,
        &si,
        &pi
    );

    if (!success) {
        DWORD err = GetLastError();
        wprintf(L"[ERROR] Failed to start process (Error Code: %lu):\n  %s\n", err, fullCommand);
        wprintf(L"Press [Enter] to exit...\n");
        (void)getchar();
        return (int)err;
    }

    /* Wait for child process to finish */
    WaitForSingleObject(pi.hProcess, INFINITE);

    DWORD exitCode = 0;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return (int)exitCode;
}
