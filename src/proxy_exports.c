#include "proxy_internal.h"

const char* Proxy_GetFakeEpicId(void);
const char* Proxy_GetFakeProductId(void);
void        Proxy_EnsureReal(void);
EOS_EResult Proxy_ForwardConnectLogin(EOS_HConnect, const void*, void*, EOS_Connect_OnLoginCallback);
EOS_EResult Proxy_ForwardAuthLogin(EOS_HAuth, const void*, void*, EOS_Auth_OnLoginCallback);
EOS_EpicAccountId  Proxy_ForwardAuthAccountByIndex(EOS_HAuth, int);
EOS_ProductUserId  Proxy_ForwardConnectUserByIndex(EOS_HConnect, int);

__declspec(dllexport) EOS_ELoginStatus EOS_Auth_GetLoginStatus(EOS_HAuth Handle, EOS_EpicAccountId LocalUserId) {
    (void)Handle; (void)LocalUserId;
    return EOS_ELoginStatus_LoggedIn;
}

__declspec(dllexport) EOS_ELoginStatus EOS_Connect_GetLoginStatus(EOS_HConnect Handle, EOS_ProductUserId LocalUserId) {
    (void)Handle; (void)LocalUserId;
    return EOS_ELoginStatus_LoggedIn;
}

__declspec(dllexport) int EOS_Auth_GetLoggedInAccountsCount(EOS_HAuth Handle) {
    (void)Handle;
    return 1;
}

__declspec(dllexport) int EOS_Connect_GetLoggedInUsersCount(EOS_HConnect Handle) {
    (void)Handle;
    return 1;
}

__declspec(dllexport) EOS_EpicAccountId EOS_Auth_GetLoggedInAccountByIndex(EOS_HAuth Handle, int Index) {
    return Proxy_ForwardAuthAccountByIndex(Handle, Index);
}

__declspec(dllexport) EOS_ProductUserId EOS_Connect_GetLoggedInUserByIndex(EOS_HConnect Handle, int Index) {
    return Proxy_ForwardConnectUserByIndex(Handle, Index);
}

__declspec(dllexport) int EOS_ProductUserId_IsValid(EOS_ProductUserId UserId) {
    (void)UserId;
    return 1;
}

__declspec(dllexport) int EOS_EpicAccountId_IsValid(EOS_EpicAccountId AccountId) {
    (void)AccountId;
    return 1;
}

__declspec(dllexport) EOS_EResult EOS_Connect_Login(
    EOS_HConnect Handle, const void* Options, void* ClientData,
    EOS_Connect_OnLoginCallback CompletionDelegate)
{
    return Proxy_ForwardConnectLogin(Handle, Options, ClientData, CompletionDelegate);
}

__declspec(dllexport) EOS_EResult EOS_Auth_Login(
    EOS_HAuth Handle, const void* Options, void* ClientData,
    EOS_Auth_OnLoginCallback CompletionDelegate)
{
    return Proxy_ForwardAuthLogin(Handle, Options, ClientData, CompletionDelegate);
}
