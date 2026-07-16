#pragma once
/*
 * EOSLANKit - tipos internos da proxy EOS (zero CRT, somente kernel32).
 * Técnica: interceptar auth EOS + forward restante via .def para EOSSDK_orig.dll
 */

typedef unsigned long       DWORD;
typedef int                 BOOL;
typedef void*               HINSTANCE;
typedef void*               HMODULE;
typedef void*               LPVOID;
typedef const char*         LPCSTR;
typedef char*               LPSTR;
typedef unsigned __int64    SIZE_T;

#define PROXY_TRUE          1
#define PROXY_FALSE         0
#define PROXY_NULL          ((void*)0)
#define PROXY_MAX_PATH      260
#define DLL_PROCESS_ATTACH  1
#define HEAP_ZERO_MEMORY    8

#define EOS_Success                     0
#define EOS_ELoginStatus_LoggedIn       2

#define PROXY_ORIG_DLL_NAME             "EOSSDK_orig.dll"
#define PROXY_IDFILE_SUFFIX             ".eoslkid"

#define GENERIC_READ                    0x80000000
#define FILE_SHARE_READ                 0x00000001
#define OPEN_EXISTING                   3
#define INVALID_HANDLE_VALUE            ((void*)(SIZE_T)-1)

/* kernel32 */
__declspec(dllimport) BOOL    __stdcall DisableThreadLibraryCalls(HMODULE h);
__declspec(dllimport) HMODULE __stdcall LoadLibraryA(LPCSTR name);
__declspec(dllimport) void*   __stdcall GetProcAddress(HMODULE h, LPCSTR name);
__declspec(dllimport) DWORD   __stdcall GetModuleFileNameA(HMODULE h, LPSTR buf, DWORD sz);
__declspec(dllimport) void*   __stdcall GetProcessHeap(void);
__declspec(dllimport) void*   __stdcall HeapAlloc(void* heap, DWORD flags, SIZE_T sz);
__declspec(dllimport) BOOL    __stdcall HeapFree(void* heap, DWORD flags, void* ptr);
__declspec(dllimport) void    __stdcall RtlMoveMemory(void* dst, const void* src, SIZE_T sz);
__declspec(dllimport) void    __stdcall RtlZeroMemory(void* dst, SIZE_T sz);
__declspec(dllimport) void*   __stdcall CreateFileA(LPCSTR name, DWORD access, DWORD share, void* sa, DWORD disp, DWORD flags, void* tmpl);
__declspec(dllimport) BOOL    __stdcall ReadFile(void* h, void* buf, DWORD to_read, DWORD* read_out, void* ovl);
__declspec(dllimport) BOOL    __stdcall CloseHandle(void* h);

typedef int   EOS_EResult;
typedef int   EOS_ELoginStatus;
typedef void* EOS_HAuth;
typedef void* EOS_HConnect;
typedef void* EOS_EpicAccountId;
typedef void* EOS_ProductUserId;
typedef void* EOS_ContinuanceToken;

typedef EOS_ELoginStatus (*PFN_GetLoginStatus)(void*, void*);
typedef int              (*PFN_GetCount)(void*);
typedef void*            (*PFN_GetUserByIndex)(void*, int);
typedef EOS_EResult      (*PFN_ConnectLogin)(void*, const void*, void*, void*);
typedef EOS_EResult      (*PFN_AuthLogin)(void*, const void*, void*, void*);

typedef struct {
    EOS_EResult          ResultCode;
    void*                ClientData;
    EOS_ProductUserId    LocalUserId;
    EOS_ContinuanceToken ContinuanceToken;
} EOS_Connect_LoginCallbackInfo;

typedef void (*EOS_Connect_OnLoginCallback)(const EOS_Connect_LoginCallbackInfo*);

typedef struct {
    EOS_EResult       ResultCode;
    void*             ClientData;
    EOS_EpicAccountId LocalUserId;
    EOS_EpicAccountId SelectedAccountId;
} EOS_Auth_LoginCallbackInfo;

typedef void (*EOS_Auth_OnLoginCallback)(const EOS_Auth_LoginCallbackInfo*);

typedef struct {
    void*                       OrigClientData;
    EOS_Connect_OnLoginCallback OrigCallback;
} ConnectCtx;

typedef struct {
    void*                    OrigClientData;
    EOS_Auth_OnLoginCallback OrigCallback;
} AuthCtx;
