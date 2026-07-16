#include "proxy_internal.h"

static char g_FakeEpicId[64]    = "EOSLANKIT_EPIC000000000000000001";
static char g_FakeProductId[64]   = "EOSLANKIT_PROD000000000000000001";
static BOOL g_IdsLoaded = PROXY_FALSE;

static HMODULE   g_hReal  = PROXY_NULL;
static HINSTANCE g_hSelf  = PROXY_NULL;

static PFN_GetLoginStatus  r_Auth_GetLoginStatus            = PROXY_NULL;
static PFN_GetCount        r_Auth_GetLoggedInAccountsCount  = PROXY_NULL;
static PFN_GetCount        r_Connect_GetLoggedInUsersCount  = PROXY_NULL;
static PFN_GetUserByIndex  r_Auth_GetLoggedInAccountByIndex = PROXY_NULL;
static PFN_GetUserByIndex  r_Connect_GetLoggedInUserByIndex = PROXY_NULL;
static PFN_ConnectLogin    r_Connect_Login                  = PROXY_NULL;
static PFN_AuthLogin       r_Auth_Login                     = PROXY_NULL;

static void* proxy_alloc(SIZE_T sz) {
    return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sz);
}

static void proxy_free(void* p) {
    HeapFree(GetProcessHeap(), 0, p);
}

static void proxy_memcpy(void* d, const void* s, SIZE_T n) {
    RtlMoveMemory(d, s, n);
}

static char* proxy_strrchr(char* s, char c) {
    char* last = PROXY_NULL;
    while (*s) {
        if (*s == c) last = s;
        s++;
    }
    return last;
}

static void proxy_strcpy(char* d, SIZE_T sz, const char* s) {
    SIZE_T i = 0;
    while (i + 1 < sz && s[i]) {
        d[i] = s[i];
        i++;
    }
    d[i] = 0;
}

const char* Proxy_GetFakeEpicId(void)    { return g_FakeEpicId; }
const char* Proxy_GetFakeProductId(void) { return g_FakeProductId; }

void Proxy_SetSelfModule(HINSTANCE hInst) {
    g_hSelf = hInst;
}

/* Le <dll>.eoslkid: 2 linhas ASCII (Epic ID, Product ID), 1..63 chars cada.
 * LF, CRLF ou LFLF entre elas. Silencioso se arquivo nao existe / malformado. */
static void Proxy_LoadIdsFromFile(void) {
    char path[PROXY_MAX_PATH];
    char buf[256];
    DWORD got = 0;
    void* h;
    SIZE_T i, line = 0, col = 0;
    char* dst;

    if (g_IdsLoaded) return;
    GetModuleFileNameA(g_hSelf, path, PROXY_MAX_PATH);
    {
        SIZE_T pl = 0;
        while (path[pl] && pl + 1 < PROXY_MAX_PATH) pl++;
        {
            const char* suf = PROXY_IDFILE_SUFFIX;
            SIZE_T sl = 0;
            while (suf[sl]) sl++;
            if (pl + sl >= PROXY_MAX_PATH) return;
            for (i = 0; i < sl; i++) path[pl + i] = suf[i];
            path[pl + sl] = 0;
        }
    }

    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, PROXY_NULL, OPEN_EXISTING, 0, PROXY_NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    if (!ReadFile(h, buf, sizeof(buf) - 1, &got, PROXY_NULL) || got == 0) {
        CloseHandle(h);
        return;
    }
    CloseHandle(h);
    buf[got] = 0;

    dst = g_FakeEpicId;
    for (i = 0; i < got; i++) {
        char c = buf[i];
        if (c == '\r') continue;
        if (c == '\n') {
            dst[col] = 0;
            if (line == 0) { dst = g_FakeProductId; line++; col = 0; continue; }
            break;
        }
        if (col + 1 < 64) { dst[col++] = c; }
    }
    dst[col] = 0;
    g_IdsLoaded = PROXY_TRUE;
}

static void Proxy_LoadRealProcs(void) {
#define GP(name) GetProcAddress(g_hReal, #name)
    r_Auth_GetLoginStatus            = (PFN_GetLoginStatus) GP(EOS_Auth_GetLoginStatus);
    r_Auth_GetLoggedInAccountsCount  = (PFN_GetCount)       GP(EOS_Auth_GetLoggedInAccountsCount);
    r_Connect_GetLoggedInUsersCount  = (PFN_GetCount)       GP(EOS_Connect_GetLoggedInUsersCount);
    r_Auth_GetLoggedInAccountByIndex = (PFN_GetUserByIndex) GP(EOS_Auth_GetLoggedInAccountByIndex);
    r_Connect_GetLoggedInUserByIndex = (PFN_GetUserByIndex) GP(EOS_Connect_GetLoggedInUserByIndex);
    r_Connect_Login                  = (PFN_ConnectLogin)   GP(EOS_Connect_Login);
    r_Auth_Login                     = (PFN_AuthLogin)      GP(EOS_Auth_Login);
#undef GP
}

void Proxy_EnsureReal(void) {
    char path[PROXY_MAX_PATH];

    if (g_hReal) return;

    /* CRÍTICO: usar g_hSelf (nossa DLL), NÃO NULL (EXE).
     * Garante EOSSDK_orig.dll no mesmo dir que a proxy. */
    GetModuleFileNameA(g_hSelf, path, PROXY_MAX_PATH);
    {
        char* slash = proxy_strrchr(path, '\\');
        if (slash)
            proxy_strcpy(slash + 1, PROXY_MAX_PATH - (SIZE_T)(slash + 1 - path), PROXY_ORIG_DLL_NAME);
    }
    g_hReal = LoadLibraryA(path);
    if (!g_hReal)
        g_hReal = LoadLibraryA(PROXY_ORIG_DLL_NAME);
    if (!g_hReal) return;

    Proxy_LoadRealProcs();
}

PFN_ConnectLogin Proxy_GetRealConnectLogin(void) { return r_Connect_Login; }
PFN_AuthLogin    Proxy_GetRealAuthLogin(void)    { return r_Auth_Login; }
PFN_GetUserByIndex Proxy_GetRealAuthAccountByIndex(void)    { return r_Auth_GetLoggedInAccountByIndex; }
PFN_GetUserByIndex Proxy_GetRealConnectUserByIndex(void)    { return r_Connect_GetLoggedInUserByIndex; }

void* Proxy_Alloc(SIZE_T sz)  { return proxy_alloc(sz); }
void  Proxy_Free(void* p)     { proxy_free(p); }
void  Proxy_Memcpy(void* d, const void* s, SIZE_T n) { proxy_memcpy(d, s, n); }

static void Proxy_ConnectCb(const EOS_Connect_LoginCallbackInfo* Info) {
    ConnectCtx* ctx = (ConnectCtx*)Info->ClientData;
    EOS_Connect_LoginCallbackInfo fake;
    proxy_memcpy(&fake, Info, sizeof(fake));
    fake.ResultCode = EOS_Success;
    fake.ClientData = ctx->OrigClientData;
    if (!fake.LocalUserId)
        fake.LocalUserId = (EOS_ProductUserId)g_FakeProductId;
    ctx->OrigCallback(&fake);
    proxy_free(ctx);
}

static void Proxy_AuthCb(const EOS_Auth_LoginCallbackInfo* Info) {
    AuthCtx* ctx = (AuthCtx*)Info->ClientData;
    EOS_Auth_LoginCallbackInfo fake;
    proxy_memcpy(&fake, Info, sizeof(fake));
    fake.ResultCode = EOS_Success;
    fake.ClientData = ctx->OrigClientData;
    if (!fake.LocalUserId)
        fake.LocalUserId = (EOS_EpicAccountId)g_FakeEpicId;
    if (!fake.SelectedAccountId)
        fake.SelectedAccountId = (EOS_EpicAccountId)g_FakeEpicId;
    ctx->OrigCallback(&fake);
    proxy_free(ctx);
}

EOS_EResult Proxy_ForwardConnectLogin(
    EOS_HConnect Handle, const void* Options, void* ClientData,
    EOS_Connect_OnLoginCallback CompletionDelegate)
{
    ConnectCtx* ctx;

    Proxy_EnsureReal();
    if (!r_Connect_Login) {
        if (CompletionDelegate) {
            EOS_Connect_LoginCallbackInfo info;
            RtlZeroMemory(&info, sizeof(info));
            info.ResultCode  = EOS_Success;
            info.ClientData  = ClientData;
            info.LocalUserId = (EOS_ProductUserId)g_FakeProductId;
            CompletionDelegate(&info);
        }
        return EOS_Success;
    }
    ctx = (ConnectCtx*)proxy_alloc(sizeof(ConnectCtx));
    if (!ctx) return -1;
    ctx->OrigClientData = ClientData;
    ctx->OrigCallback   = CompletionDelegate;
    return r_Connect_Login(Handle, Options, ctx, (void*)Proxy_ConnectCb);
}

EOS_EResult Proxy_ForwardAuthLogin(
    EOS_HAuth Handle, const void* Options, void* ClientData,
    EOS_Auth_OnLoginCallback CompletionDelegate)
{
    AuthCtx* ctx;

    Proxy_EnsureReal();
    if (!r_Auth_Login) {
        if (CompletionDelegate) {
            EOS_Auth_LoginCallbackInfo info;
            RtlZeroMemory(&info, sizeof(info));
            info.ResultCode        = EOS_Success;
            info.ClientData        = ClientData;
            info.LocalUserId       = (EOS_EpicAccountId)g_FakeEpicId;
            info.SelectedAccountId = (EOS_EpicAccountId)g_FakeEpicId;
            CompletionDelegate(&info);
        }
        return EOS_Success;
    }
    ctx = (AuthCtx*)proxy_alloc(sizeof(AuthCtx));
    if (!ctx) return -1;
    ctx->OrigClientData = ClientData;
    ctx->OrigCallback   = CompletionDelegate;
    return r_Auth_Login(Handle, Options, ctx, (void*)Proxy_AuthCb);
}

EOS_EpicAccountId Proxy_ForwardAuthAccountByIndex(EOS_HAuth Handle, int Index) {
    Proxy_EnsureReal();
    if (r_Auth_GetLoggedInAccountByIndex) {
        EOS_EpicAccountId id = r_Auth_GetLoggedInAccountByIndex(Handle, Index);
        if (id) return id;
    }
    return (EOS_EpicAccountId)g_FakeEpicId;
}

EOS_ProductUserId Proxy_ForwardConnectUserByIndex(EOS_HConnect Handle, int Index) {
    Proxy_EnsureReal();
    if (r_Connect_GetLoggedInUserByIndex) {
        EOS_ProductUserId id = r_Connect_GetLoggedInUserByIndex(Handle, Index);
        if (id) return id;
    }
    return (EOS_ProductUserId)g_FakeProductId;
}

BOOL __stdcall DllMain(HINSTANCE hInst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hInst);
        Proxy_SetSelfModule(hInst);
        Proxy_LoadIdsFromFile();
        Proxy_EnsureReal();
    }
    return PROXY_TRUE;
}
